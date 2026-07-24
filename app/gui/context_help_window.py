"""Searchable non-modal local Context Help and glossary."""

from __future__ import annotations

import customtkinter as ctk

from app.core.app_metadata import METADATA


class ContextHelpWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        theme,
        registry,
        *,
        interface_mode_provider=lambda: "guided",
        on_close=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.registry = registry
        self.interface_mode_provider = interface_mode_provider
        self.on_close = on_close
        self.current_topic = None
        self.title(f"{METADATA.application_name} — Contextual Help")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 650)
        self.geometry(self._center(980, 650))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Control-f>", lambda _event: self.search.focus_set())
        self.bind("<Escape>", lambda _event: self.close())
        self._build_header()
        self._build_tabs()
        self._render_topic_list()
        self._render_glossary()

    def _center(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width, height = min(width, screen_width), min(height, screen_height)
        return (
            f"{width}x{height}+{max(0, (screen_width-width)//2)}"
            f"+{max(0, (screen_height-height)//2)}"
        )

    def _build_header(self):
        header = ctk.CTkFrame(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="CONTEXTUAL HELP",
            text_color=self.theme["gold"],
            font=("Times New Roman", 25, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 2))
        self.mode_label = ctk.CTkLabel(
            header, text="", text_color=self.theme["muted"], anchor="e",
        )
        self.mode_label.grid(row=0, column=1, padx=10)
        self.search = ctk.CTkEntry(
            header,
            placeholder_text="Search help and glossary locally…",
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.search.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 8)
        )
        self.search.bind("<KeyRelease>", lambda _event: self._search_changed())

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self,
            fg_color=self.theme["panel"],
            border_width=1,
            border_color=self.theme["border"],
            segmented_button_fg_color=self.theme["panel_alt"],
            segmented_button_selected_color=self.theme["red"],
            segmented_button_selected_hover_color=self.theme["red_hover"],
            segmented_button_unselected_color=self.theme["panel_alt"],
            segmented_button_unselected_hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
        self.topic_tab = self.tabs.add("Topics")
        self.glossary_tab = self.tabs.add("Glossary")
        for tab in (self.topic_tab, self.glossary_tab):
            tab.configure(fg_color=self.theme["bg"])
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(1, weight=1)
        self.topic_list = ctk.CTkScrollableFrame(
            self.topic_tab,
            width=260,
            fg_color=self.theme["panel_alt"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.topic_list.grid(row=0, column=0, sticky="ns", padx=(6, 3), pady=6)
        self.topic_list.grid_columnconfigure(0, weight=1)
        self.topic_text = self._text(self.topic_tab)
        self.topic_text.grid(row=0, column=1, sticky="nsew", padx=(3, 6), pady=6)
        self.glossary_list = ctk.CTkScrollableFrame(
            self.glossary_tab,
            width=260,
            fg_color=self.theme["panel_alt"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        self.glossary_list.grid(
            row=0, column=0, sticky="ns", padx=(6, 3), pady=6
        )
        self.glossary_list.grid_columnconfigure(0, weight=1)
        self.glossary_text = self._text(self.glossary_tab)
        self.glossary_text.grid(
            row=0, column=1, sticky="nsew", padx=(3, 6), pady=6
        )

    def _text(self, parent):
        widget = ctk.CTkTextbox(
            parent,
            fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"],
            border_width=1,
            border_color=self.theme["border"],
            wrap="word",
            font=("Segoe UI", 12),
        )
        widget.configure(state="disabled")
        return widget

    @staticmethod
    def _set_text(widget, text):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _search_changed(self):
        self._render_topic_list()
        self._render_glossary()

    def _render_topic_list(self):
        for child in self.topic_list.winfo_children():
            child.destroy()
        topics = self.registry.search_topics(self.search.get())
        for row, topic in enumerate(topics):
            ctk.CTkButton(
                self.topic_list,
                text=topic.title,
                command=lambda item=topic: self.show_topic(item.topic_id),
                anchor="w",
                fg_color=(
                    self.theme["red"]
                    if topic is self.current_topic else self.theme["panel_alt"]
                ),
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"],
                border_width=1,
                border_color=self.theme["border"],
            ).grid(row=row, column=0, sticky="ew", padx=3, pady=3)
        if not topics:
            ctk.CTkLabel(
                self.topic_list,
                text="No matching help topics.",
                text_color=self.theme["muted"],
                wraplength=220,
            ).grid(row=0, column=0, padx=8, pady=16)

    def _render_glossary(self):
        for child in self.glossary_list.winfo_children():
            child.destroy()
        entries = self.registry.search_glossary(self.search.get())
        for row, entry in enumerate(entries):
            ctk.CTkButton(
                self.glossary_list,
                text=entry.term,
                command=lambda item=entry: self.show_glossary(item),
                anchor="w",
                fg_color=self.theme["panel_alt"],
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"],
                border_width=1,
                border_color=self.theme["border"],
            ).grid(row=row, column=0, sticky="ew", padx=3, pady=3)
        if entries:
            self.show_glossary(entries[0])
        else:
            self._set_text(self.glossary_text, "No matching glossary entries.")

    def show_topic(self, topic_id):
        topic = self.registry.get(topic_id)
        if topic is None:
            return
        self.current_topic = topic
        self.mode_label.configure(
            text=f"Interface mode: {self.interface_mode_provider().title()}"
        )
        sections = (
            ("Purpose", (topic.purpose,)),
            ("Prerequisites", topic.prerequisites),
            ("Quick Start", topic.quick_start),
            ("Controls", topic.controls),
            ("Terminology", topic.terminology),
            ("Empty States", topic.empty_states),
            ("Common Errors", topic.common_errors),
            ("Safe Example", (topic.safe_example,)),
            ("Related Tools", topic.related_tools),
            ("Guided / Advanced", (topic.mode_notes,)),
        )
        text = topic.title + "\n" + "=" * len(topic.title)
        for title, values in sections:
            text += f"\n\n{title}\n" + "\n".join(
                f"• {value}" for value in values
            )
        self._set_text(self.topic_text, text)
        self.tabs.set("Topics")
        self._render_topic_list()
        self.deiconify()
        self.lift()

    def show_glossary(self, entry):
        self._set_text(
            self.glossary_text,
            f"{entry.term}\n{'=' * len(entry.term)}\n\n"
            f"{entry.definition}\n\nRelated: "
            f"{', '.join(entry.related_terms) or 'None'}",
        )

    def close(self):
        if self.on_close:
            self.on_close()
        self.destroy()
