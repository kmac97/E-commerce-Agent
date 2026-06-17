# utils/formatter.py
# Handles printing nicely formatted output to the terminal

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

console = Console() if RICH_AVAILABLE else None


def print_welcome():
    """Print the welcome banner."""
    if RICH_AVAILABLE:
        console.print(Panel.fit(
            "[bold cyan]🛒 E-commerce AI Assistant[/bold cyan]\n"
            "[dim]Your practical business advisor — powered by AI[/dim]\n\n"
            "[green]Commands:[/green]\n"
            "  Just type your question or product idea\n"
            "  [yellow]save[/yellow]     → Save the last response to your research folder\n"
            "  [yellow]list[/yellow]     → Show all saved research\n"
            "  [yellow]clear[/yellow]    → Clear the screen\n"
            "  [yellow]quit[/yellow]     → Exit",
            border_style="cyan",
        ))
    else:
        print("\n" + "="*60)
        print("  E-commerce AI Assistant")
        print("  Your practical business advisor")
        print("="*60)
        print("Commands: save | list | clear | quit")
        print()


def print_response(text: str):
    """Print the assistant response with formatting."""
    if RICH_AVAILABLE:
        console.print()
        console.print(Panel(
            Markdown(text),
            title="[bold green]Assistant[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))
    else:
        print("\n--- Assistant ---")
        print(text)
        print("-" * 40)


def print_user_prompt():
    """Print the user input prompt."""
    if RICH_AVAILABLE:
        console.print("\n[bold cyan]You:[/bold cyan] ", end="")
    else:
        print("\nYou: ", end="")


def print_thinking():
    """Print a thinking indicator."""
    if RICH_AVAILABLE:
        console.print("[dim]Thinking...[/dim]")
    else:
        print("Thinking...")


def print_saved(filepath: str):
    """Print a success message when saving."""
    if RICH_AVAILABLE:
        console.print(f"[bold green]✅ Saved to:[/bold green] [dim]{filepath}[/dim]")
    else:
        print(f"Saved to: {filepath}")


def print_error(message: str):
    """Print an error message."""
    if RICH_AVAILABLE:
        console.print(f"[bold red]❌ Error:[/bold red] {message}")
    else:
        print(f"Error: {message}")


def print_info(message: str):
    """Print an info message."""
    if RICH_AVAILABLE:
        console.print(f"[dim]{message}[/dim]")
    else:
        print(message)


def print_saved_list(items: list):
    """Print a list of saved research items."""
    if not items:
        print_info("No saved research yet. Ask a question and type 'save' to save it.")
        return

    if RICH_AVAILABLE:
        from rich.table import Table
        table = Table(title="Saved Research", box=box.SIMPLE)
        table.add_column("Category", style="cyan")
        table.add_column("Topic", style="white")
        table.add_column("Saved At", style="dim")
        for item in items:
            table.add_row(item["category"], item["topic"], item["saved_at"][:16])
        console.print(table)
    else:
        print("\nSaved Research:")
        print("-" * 50)
        for item in items:
            print(f"[{item['category']}] {item['topic']} — {item['saved_at'][:16]}")
