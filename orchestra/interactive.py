"""
Interactive collection builder for Orchestra.

This module provides a wizard-style interface for creating new test collections,
making it easy for new users to get started without memorizing YAML syntax.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

console = Console()


class CollectionBuilder:
    """Interactive builder for creating Orchestra test collections."""
    
    def __init__(self):
        self.name: str = ""
        self.transport: str = ""
        self.url: Optional[str] = None
        self.command: Optional[str] = None
        self.args: list[str] = []
        self.auth_type: Optional[str] = None
        self.steps: list[dict] = []
    
    def run(self) -> str:
        """Run the interactive wizard and return YAML content."""
        self._welcome()
        self._ask_basics()
        self._ask_transport()
        self._ask_auth()
        self._ask_steps()
        return self._generate_yaml()
    
    def _welcome(self):
        """Display welcome message."""
        console.print()
        console.print(Panel.fit(
            "[bold cyan]🎵 Orchestra Collection Builder[/bold cyan]\n\n"
            "This wizard will help you create a new test collection.\n"
            "Answer a few questions, and we'll generate the YAML for you!",
            border_style="cyan"
        ))
        console.print()
    
    def _ask_basics(self):
        """Ask for collection name."""
        self.name = Prompt.ask(
            "[bold]What would you like to name this collection?[/bold]",
            default="My MCP Test"
        )
        console.print(f"✓ Collection name: [green]{self.name}[/green]\n")
    
    def _ask_transport(self):
        """Ask about transport type."""
        console.print("[bold]How does your MCP server run?[/bold]")
        console.print("  1. [cyan]Local (STDIO)[/cyan] - Runs as a subprocess (e.g., npx, python)")
        console.print("  2. [cyan]Remote (HTTP)[/cyan] - Cloud-hosted server with a URL")
        console.print("  3. [cyan]SSE[/cyan] - Server-Sent Events\n")
        
        choice = Prompt.ask(
            "Choose transport type",
            choices=["1", "2", "3"],
            default="2"
        )
        
        if choice == "1":
            self.transport = "stdio"
            self._ask_stdio_details()
        elif choice == "2":
            self.transport = "http"
            self._ask_http_details()
        else:
            self.transport = "sse"
            self._ask_http_details()
        
        console.print()
    
    def _ask_stdio_details(self):
        """Ask for STDIO-specific configuration."""
        console.print("\n[bold]Local Server Configuration[/bold]")
        
        # Common patterns
        console.print("\nCommon patterns:")
        console.print("  1. [dim]npx -y @modelcontextprotocol/server-name[/dim]")
        console.print("  2. [dim]python -m my_server[/dim]")
        console.print("  3. [dim]node server.js[/dim]")
        console.print("  4. [dim]Custom command[/dim]\n")
        
        pattern = Prompt.ask("Choose a pattern", choices=["1", "2", "3", "4"], default="1")
        
        if pattern == "1":
            package = Prompt.ask("Enter npx package name", default="@modelcontextprotocol/server-memory")
            self.command = "npx"
            self.args = ["-y", package]
        elif pattern == "2":
            module = Prompt.ask("Enter Python module name", default="my_server")
            self.command = "python"
            self.args = ["-m", module]
        elif pattern == "3":
            script = Prompt.ask("Enter Node.js script path", default="server.js")
            self.command = "node"
            self.args = [script]
        else:
            self.command = Prompt.ask("Enter command", default="python")
            args_str = Prompt.ask("Enter arguments (space-separated)", default="server.py")
            self.args = args_str.split()
        
        console.print(f"✓ Command: [green]{self.command} {' '.join(self.args)}[/green]")
    
    def _ask_http_details(self):
        """Ask for HTTP-specific configuration."""
        console.print("\n[bold]Remote Server Configuration[/bold]")
        
        self.url = Prompt.ask(
            "Enter server URL",
            default="https://api.example.com/mcp"
        )
        
        console.print(f"✓ URL: [green]{self.url}[/green]")
    
    def _ask_auth(self):
        """Ask about authentication."""
        console.print("\n[bold]Does your server require authentication?[/bold]")
        
        needs_auth = Confirm.ask("Add authentication?", default=False)
        
        if needs_auth:
            console.print("\n  1. [cyan]Bearer Token[/cyan] - Authorization: Bearer <token>")
            console.print("  2. [cyan]API Key[/cyan] - X-API-Key: <key>")
            console.print("  3. [cyan]Basic Auth[/cyan] - Username and password\n")
            
            choice = Prompt.ask("Choose auth type", choices=["1", "2", "3"], default="1")
            
            if choice == "1":
                self.auth_type = "bearer"
                console.print("✓ Using Bearer token (set via environment variable)")
            elif choice == "2":
                self.auth_type = "api_key"
                console.print("✓ Using API Key (set via environment variable)")
            else:
                self.auth_type = "basic"
                console.print("✓ Using Basic auth (set via environment variables)")
        
        console.print()
    
    def _ask_steps(self):
        """Ask about test steps."""
        console.print("[bold]Would you like to add test steps now?[/bold]")
        console.print("[dim]You can add these later by editing the YAML file[/dim]\n")
        
        add_steps = Confirm.ask("Add test steps?", default=True)
        
        if add_steps:
            console.print("\n[bold cyan]💡 Tip:[/bold cyan] Run [cyan]orchestra inspect[/cyan] on your generated file")
            console.print("   to discover available tools and their parameters!\n")
            
            add_example = Confirm.ask("Add an example tool call step?", default=True)
            
            if add_example:
                tool_name = Prompt.ask("Enter tool name", default="example_tool")
                self.steps.append({
                    "id": "call_tool",
                    "type": "tool_call",
                    "tool": tool_name,
                    "input": {},
                    "save": "$"
                })
                self.steps.append({
                    "id": "verify_success",
                    "type": "assert",
                    "from": "call_tool",
                    "check": {
                        "op": "no_error"
                    }
                })
                console.print("✓ Added example tool call + assertion")
        
        console.print()
    
    def _generate_yaml(self) -> str:
        """Generate YAML content from collected information."""
        lines = [
            "# Orchestra Test Collection",
            f"# Generated by: orchestra new",
            "# Edit this file to customize your tests",
            "",
            "version: 1",
            f'name: "{self.name}"',
            "",
            "server:",
            f'  transport: "{self.transport}"',
        ]
        
        # Add transport-specific config
        if self.transport == "stdio":
            lines.append(f'  command: "{self.command}"')
            args_yaml = ", ".join(f'"{arg}"' for arg in self.args)
            lines.append(f"  args: [{args_yaml}]")
        else:
            lines.append(f'  url: "{self.url}"')
        
        # Add auth if needed
        if self.auth_type:
            lines.append("  auth:")
            lines.append(f'    type: "{self.auth_type}"')
            
            if self.auth_type == "bearer":
                lines.append('    token: "{{env.API_TOKEN}}"')
            elif self.auth_type == "api_key":
                lines.append('    key: "{{env.API_KEY}}"')
            else:  # basic
                lines.append('    username: "{{env.USERNAME}}"')
                lines.append('    password: "{{env.PASSWORD}}"')
        
        # Add defaults
        lines.extend([
            "",
            "defaults:",
            "  timeout_ms: 30000",
            "  retries: 0",
            "",
        ])
        
        # Add steps
        if self.steps:
            lines.append("steps:")
            for step in self.steps:
                lines.append(f"  - id: {step['id']}")
                lines.append(f"    type: {step['type']}")
                
                if step['type'] == 'tool_call':
                    lines.append(f"    tool: \"{step['tool']}\"")
                    lines.append("    input:")
                    lines.append("      # Add your parameters here")
                    lines.append(f"    save: \"{step['save']}\"")
                else:  # assert
                    lines.append(f"    from: \"{step['from']}\"")
                    lines.append("    check:")
                    lines.append(f"      op: \"{step['check']['op']}\"")
                
                lines.append("")
        else:
            lines.extend([
                "steps:",
                "  # Add your test steps here",
                "  # Run 'orchestra inspect' to discover available tools",
                "  #",
                "  # - id: my_step",
                "  #   type: tool_call",
                "  #   tool: \"tool_name\"",
                "  #   input:",
                "  #     param: \"value\"",
                "  #   save: \"$\"",
                "",
            ])
        
        return "\n".join(lines)


def build_collection_interactive(output_file: Path) -> bool:
    """
    Run the interactive collection builder.
    
    Args:
        output_file: Path where the YAML should be saved
    
    Returns:
        True if collection was created successfully
    """
    builder = CollectionBuilder()
    yaml_content = builder.run()
    
    # Show preview
    console.print("[bold]📄 Generated Collection:[/bold]\n")
    console.print(Panel(yaml_content, border_style="green", expand=False))
    console.print()
    
    # Confirm save
    should_save = Confirm.ask(
        f"Save to [cyan]{output_file}[/cyan]?",
        default=True
    )
    
    if should_save:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(yaml_content)
        
        console.print(f"\n✅ Collection saved to [green]{output_file}[/green]")
        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print(f"  1. Run [cyan]orchestra inspect {output_file}[/cyan] to discover tools")
        console.print(f"  2. Edit [cyan]{output_file}[/cyan] to add your test steps")
        console.print(f"  3. Run [cyan]orchestra run {output_file}[/cyan] to execute tests")
        console.print()
        
        return True
    else:
        console.print("\n[yellow]Collection not saved[/yellow]")
        return False

