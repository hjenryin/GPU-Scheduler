from typing import List, Dict, Tuple, Optional
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, Button, TextArea
from textual.containers import Container, Horizontal
from rich.text import Text
import re

class GitDiffScreen(Screen):
    """Screen to show git diff in raw text view"""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
    ]

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
        self.raw_diff = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"Git Diff for Job {self.job_id}", id="diff-title"),
            Horizontal(
                Button("Compare Start vs End", id="diff-end-button", variant="primary"),
                Button("Compare Start vs Current", id="diff-current-button", variant="default"),
                id="diff-controls",
                classes="mb-2"
            ),
            TextArea("", id="diff-content", read_only=True, language="diff"),
            Button("Back", id="back-button", classes="mt-2"),
            id="diff-container"
        )
        yield Footer()

    def on_mount(self):
        """Load default diff (Start vs End)"""
        # Style the layout
        self.query_one("#diff-container").styles.height = "100%"
        self.query_one("#diff-content").styles.height = "1fr"
        self.query_one("#diff-content").styles.border = ("solid", "gray")
        
        # Load initial data
        self.action_show_diff("end")

    def action_show_diff(self, compare_with: str):
        """Fetch and display raw diff"""
        # Update button variants
        self.query_one("#diff-end-button", Button).variant = "primary" if compare_with == "end" else "default"
        self.query_one("#diff-current-button", Button).variant = "primary" if compare_with == "current" else "default"

        try:
            if hasattr(self.app, "client"):
                self.raw_diff = self.app.client.get_job_diff(self.job_id, compare_with)
                self.query_one("#diff-content", TextArea).load_text(self.raw_diff or "No changes.")
            else:
                self.query_one("#diff-content", TextArea).load_text("Error: API client not available")
        except Exception as e:
            self.query_one("#diff-content", TextArea).load_text(f"Error fetching diff: {e}")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "diff-end-button":
            self.action_show_diff("end")
        elif event.button.id == "diff-current-button":
            self.action_show_diff("current")
        elif event.button.id == "back-button":
            self.app.pop_screen()
