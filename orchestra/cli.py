#!/usr/bin/env python3
"""
Orchestra CLI - MCP Server Testing Tool

Usage:
    orchestra run <collection.yaml> [OPTIONS]
    orchestra validate <collection.yaml>
    orchestra --version
"""

import asyncio
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .schema_parsing import (
    load_collection,
    Collection,
    ToolCallStep,
    AssertStep,
    AssertOp,
    AuthConfig,
    AuthType,
)
from .transport import (
    create_transport,
    ToolCallRequest,
    STDIOTransport,
    HTTPTransport,
    SSETransport,
)
from .assertions import AssertionEngine
from .reporting import Reporter, StepStatus

# Suppress asyncio subprocess cleanup warnings
warnings.filterwarnings("ignore", message=".*Event loop is closed.*")

app = typer.Typer(
    name="orchestra",
    help="🎵 Orchestra - MCP Server Testing and Orchestration Tool",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"🎵 Orchestra v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit"
    ),
):
    """
    🎵 Orchestra - MCP Server Testing and Orchestration Tool
    
    Test MCP servers with declarative YAML collections.
    """
    pass


def interpolate_value(value, env: dict, results: dict):
    """Interpolate template variables in a value."""
    if isinstance(value, str):
        pattern = r"\{\{env\.(\w+)\}\}"
        def replace_env(match):
            var_name = match.group(1)
            return str(env.get(var_name, match.group(0)))
        return re.sub(pattern, replace_env, value)
    elif isinstance(value, dict):
        return {k: interpolate_value(v, env, results) for k, v in value.items()}
    elif isinstance(value, list):
        return [interpolate_value(v, env, results) for v in value]
    return value


def interpolate_auth_config(auth: AuthConfig | None, env: dict) -> AuthConfig | None:
    """Interpolate environment variables in auth config."""
    if auth is None:
        return None
    return AuthConfig(
        type=auth.type,
        token=interpolate_value(auth.token, env, {}) if auth.token else None,
        header=auth.header,
        key=interpolate_value(auth.key, env, {}) if auth.key else None,
        username=interpolate_value(auth.username, env, {}) if auth.username else None,
        password=interpolate_value(auth.password, env, {}) if auth.password else None,
    )


async def run_collection_async(
    collection: Collection,
    verbose: bool = True,
    quiet: bool = False,
    show_responses: bool = False,
) -> Reporter:
    """Execute a collection and return the reporter with results."""
    reporter = Reporter.from_collection(collection)
    reporter.start_run()
    engine = AssertionEngine()
    step_results: dict[str, any] = {}
    
    # Interpolate auth config
    interpolated_auth = interpolate_auth_config(collection.server.auth, collection.env)
    
    # Interpolate server env vars (for STDIO transport)
    interpolated_server_env = {
        key: interpolate_value(value, collection.env, {})
        for key, value in collection.server.env.items()
    }
    
    # Create transport based on type
    transport_type = collection.server.transport.value
    if transport_type == "stdio":
        transport = STDIOTransport(
            command=collection.server.command,
            args=collection.server.args,
            env=interpolated_server_env,
        )
    elif transport_type == "sse":
        transport = SSETransport(
            base_url=collection.server.url,
            auth_config=interpolated_auth,
        )
    else:  # http
        transport = HTTPTransport(
            url=collection.server.url,
            auth_config=interpolated_auth,
        )
    
    if verbose and not quiet:
        console.print(f"\n{'='*60}")
        console.print(f"  [bold]Running:[/bold] {collection.name}")
        console.print(f"  [bold]Server:[/bold] {collection.server.transport.value}")
        console.print(f"  [bold]Steps:[/bold] {len(collection.steps)}")
        console.print(f"{'='*60}\n")
    
    try:
        # Connect
        if verbose and not quiet:
            console.print("📡 Connecting to MCP server...")
        await transport.connect()
        
        # Initialize
        init_response = await transport.initialize()
        if not init_response.success:
            if not quiet:
                console.print(f"[red]❌ Failed to initialize:[/red] {init_response.error}")
            reporter.complete_step_error("_init", "Failed to initialize MCP connection")
            return reporter
        
        if verbose and not quiet:
            info = init_response.result.get("serverInfo", {})
            console.print(f"   [green]✅ Connected to {info.get('name', '?')} v{info.get('version', '?')}[/green]\n")
        
        # Execute each step
        for step in collection.steps:
            if verbose and not quiet:
                console.print(f"▶ [bold]Step:[/bold] {step.id} ({step.type.value})")
            
            reporter.start_step(step.id)
            
            try:
                if isinstance(step, ToolCallStep):
                    input_data = interpolate_value(step.input, collection.env, step_results)
                    
                    if verbose and not quiet:
                        console.print(f"  Tool: {step.tool}")
                        console.print(f"  Input: {json.dumps(input_data)[:80]}...")
                    
                    response = await transport.call_tool(ToolCallRequest(
                        tool_name=step.tool,
                        arguments=input_data,
                        timeout_ms=collection.defaults.timeout_ms,
                    ))
                    
                    if response.success:
                        result = response.result
                        
                        # Always store the raw response for assertions
                        step_results[step.id] = result
                        
                        # Check for MCP error in the response
                        is_mcp_error = result.get("isError", False) if isinstance(result, dict) else False
                        
                        reporter.complete_step_success(step.id, output=result)
                        
                        if verbose and not quiet:
                            if is_mcp_error:
                                # Extract error message from content
                                error_msg = "Unknown MCP error"
                                if isinstance(result, dict) and "content" in result:
                                    content = result["content"]
                                    if isinstance(content, list) and len(content) > 0:
                                        error_msg = content[0].get("text", error_msg)
                                console.print(f"  [yellow]⚠️  Tool returned error:[/yellow] {error_msg}")
                            else:
                                console.print(f"  [green]✅ Success[/green]")
                            
                            # Show response if flag is set
                            if show_responses and result:
                                console.print(f"  [dim]Response:[/dim]")
                                response_str = json.dumps(result, indent=2)
                                # Truncate if too long
                                if len(response_str) > 500:
                                    console.print(f"  [dim]{response_str[:500]}...[/dim]")
                                    console.print(f"  [dim]  (truncated, {len(response_str)} total chars)[/dim]")
                                else:
                                    console.print(f"  [dim]{response_str}[/dim]")
                    else:
                        error_msg = response.error.message if response.error else "Unknown error"
                        reporter.complete_step_error(step.id, error_msg)
                        if not quiet:
                            console.print(f"  [red]❌ Error:[/red] {error_msg}")
                
                elif isinstance(step, AssertStep):
                    source_data = step_results.get(step.from_step)
                    
                    if source_data is None:
                        reporter.complete_step_error(
                            step.id, 
                            f"Source step '{step.from_step}' has no results"
                        )
                        if not quiet:
                            console.print(f"  [red]❌ No data from step '{step.from_step}'[/red]")
                        continue
                    
                    if verbose and not quiet:
                        console.print(f"  Asserting on: {step.from_step}")
                        console.print(f"  Check: {step.check.op.value} at {step.check.path}")
                    
                    check = step.check
                    if check.op == AssertOp.JSONPATH_EXISTS:
                        result = engine.exists(source_data, check.path)
                    elif check.op == AssertOp.JSONPATH_EQ:
                        result = engine.equals(source_data, check.path, check.value)
                    elif check.op == AssertOp.JSONPATH_CONTAINS:
                        result = engine.contains(source_data, check.path, check.value)
                    elif check.op == AssertOp.JSONPATH_LEN_GTE:
                        result = engine.length_gte(source_data, check.path, check.value)
                    elif check.op == AssertOp.JSONPATH_LEN_LTE:
                        result = engine.length_lte(source_data, check.path, check.value)
                    elif check.op == AssertOp.JSONPATH_LEN_EQ:
                        result = engine.length_eq(source_data, check.path, check.value)
                    elif check.op == AssertOp.IS_ERROR:
                        result = engine.is_error(source_data)
                    elif check.op == AssertOp.NO_ERROR:
                        result = engine.no_error(source_data)
                    else:
                        reporter.complete_step_error(step.id, f"Unknown assertion op: {check.op}")
                        continue
                    
                    if result.passed:
                        reporter.complete_step_success(step.id, actual_value=result.actual)
                        if verbose and not quiet:
                            console.print(f"  [green]✅ Passed[/green]")
                    else:
                        reporter.complete_step_failure(
                            step.id,
                            failure_message=result.message,
                            expected_value=result.expected,
                            actual_value=result.actual,
                        )
                        if not quiet:
                            console.print(f"  [red]❌ Failed:[/red] {result.message}")
                
            except Exception as e:
                reporter.complete_step_error(step.id, f"{type(e).__name__}: {e}")
                if not quiet:
                    console.print(f"  [red]❌ Error:[/red] {type(e).__name__}: {e}")
            
            # Apply delay if specified for this step
            if step.delay_ms and step.delay_ms > 0:
                if verbose and not quiet:
                    console.print(f"  [dim]⏱️  Waiting {step.delay_ms}ms...[/dim]")
                await asyncio.sleep(step.delay_ms / 1000.0)
            
            if verbose and not quiet:
                console.print()
    
    except Exception as e:
        if not quiet:
            console.print(f"\n[red]❌ Fatal error:[/red] {type(e).__name__}: {e}")
    
    finally:
        if verbose and not quiet:
            console.print("👋 Disconnecting...")
        await transport.disconnect()
    
    reporter.finish_run()
    return reporter


@app.command()
def run(
    collection_file: Path = typer.Argument(
        ...,
        help="Path to the collection YAML file",
        exists=True,
        readable=True,
    ),
    verbose: bool = typer.Option(
        True, "--verbose/--no-verbose", "-V",
        help="Show detailed step output"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Only show errors and final status"
    ),
    show_responses: bool = typer.Option(
        False, "--show-responses", "-r",
        help="Show tool call responses (can be verbose)"
    ),
    output: str = typer.Option(
        "text", "--output", "-o",
        help="Output format: text or json"
    ),
    report_dir: Path = typer.Option(
        Path("reports"), "--report-dir", "-R",
        help="Directory to save JSON reports"
    ),
    no_report: bool = typer.Option(
        False, "--no-report",
        help="Don't save a JSON report file"
    ),
):
    """
    Run an MCP test collection.
    
    Execute all steps in the collection, perform assertions,
    and generate a run report.
    """
    if not quiet:
        console.print(f"\n📄 Loading collection: {collection_file}")
    
    # Load and validate
    collection, validation = load_collection(str(collection_file))
    
    if not validation.is_valid:
        console.print(f"\n[red]❌ Validation failed:[/red]")
        console.print(str(validation))
        raise typer.Exit(code=1)
    
    if not quiet:
        console.print(f"   [green]✅ Valid collection:[/green] {collection.name}")
    
    # Run the collection
    reporter = asyncio.run(run_collection_async(collection, verbose, quiet, show_responses))
    report = reporter.report
    
    # Output results
    if output == "json":
        console.print_json(data=report.to_dict())
    else:
        if not quiet:
            console.print("\n" + report.summary())
    
    # Save report
    if not no_report:
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"{report.run_id}.json"
        reporter.save_json(report_path)
        if not quiet:
            console.print(f"\n📁 Report saved: {report_path}")
    
    # Exit with appropriate code
    if report.status.value == "passed":
        raise typer.Exit(code=0)
    else:
        raise typer.Exit(code=1)


@app.command()
def validate(
    collection_file: Path = typer.Argument(
        ...,
        help="Path to the collection YAML file",
        exists=True,
        readable=True,
    ),
):
    """
    Validate a collection YAML file.
    
    Check the schema and report any errors without running the collection.
    """
    console.print(f"\n📄 Validating: {collection_file}")
    
    collection, validation = load_collection(str(collection_file))
    
    if validation.is_valid:
        console.print(f"\n[green]✅ Valid collection:[/green] {collection.name}")
        console.print(f"   Server: {collection.server.transport.value}")
        console.print(f"   Steps: {len(collection.steps)}")
        
        # Show steps summary
        table = Table(title="Steps")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Details")
        
        for step in collection.steps:
            if isinstance(step, ToolCallStep):
                details = f"tool: {step.tool}"
            elif isinstance(step, AssertStep):
                details = f"from: {step.from_step}, op: {step.check.op.value}"
            else:
                details = ""
            table.add_row(step.id, step.type.value, details)
        
        console.print()
        console.print(table)
        raise typer.Exit(code=0)
    else:
        console.print(f"\n[red]❌ Validation failed:[/red]")
        console.print(str(validation))
        raise typer.Exit(code=1)


@app.command()
def info():
    """
    Show information about Orchestra.
    """
    console.print(f"""
🎵 [bold]Orchestra[/bold] v{__version__}

MCP Server Testing and Orchestration Tool

[bold]Features:[/bold]
  • Declarative YAML test collections
  • STDIO, Streamable HTTP, and SSE transports
  • JSONPath-based assertions
  • Authentication support (Bearer, API Key, Basic)
  • Detailed JSON run reports

[bold]Quick Start:[/bold]
  orchestra run schemas/test.yaml
  orchestra validate schemas/test.yaml

[bold]Documentation:[/bold]
  https://github.com/ahaanc/orchestra
""")


if __name__ == "__main__":
    app()

