"""Local-only Learning Center for educational addon courses and glossary."""

from __future__ import annotations

import customtkinter as ctk

from app.core.app_metadata import METADATA
from app.gui.customtkinter_compat import PendingCallbackOwner, widget_exists


class LearningCenterWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent,
        theme,
        service,
        help_registry,
        *,
        open_addons=None,
        open_help=None,
        interface_mode_provider=lambda: "guided",
        on_close=None,
    ):
        super().__init__(parent)
        self.theme = theme
        self.service = service
        self.help_registry = help_registry
        self.open_addons = open_addons
        self.open_help = open_help
        self.interface_mode_provider = interface_mode_provider
        self.on_close = on_close
        self.current_course = None
        self.current_lesson = None
        self.context_topic = ""
        self.callbacks = PendingCallbackOwner(self)
        self.title(f"{METADATA.application_name} — Learning Center")
        self.configure(fg_color=theme["bg"])
        self.minsize(900, 650)
        self.geometry(self._center(1180, 780))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Control-f>", lambda _event: self.search.focus_set())
        self.bind("<Escape>", lambda _event: self.close())
        self._build_header()
        self._build_tabs()
        self.unsubscribe = service.plugin_manager.subscribe(
            lambda _event, _plugin_id: self.callbacks.schedule(0, self.refresh)
        )
        self.refresh()

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
            header, text="LEARNING CENTER",
            text_color=self.theme["gold"],
            font=("Times New Roman", 26, "bold"), anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 2))
        self.mode = ctk.CTkLabel(
            header, text="", text_color=self.theme["muted"], anchor="e"
        )
        self.mode.grid(row=0, column=1, padx=8)
        ctk.CTkButton(
            header, text="Help",
            command=lambda: self.open_help("learning-center")
            if self.open_help else None,
            width=90, fg_color=self.theme["red"],
            hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"],
        ).grid(row=0, column=2, padx=8)
        self.search = ctk.CTkEntry(
            header, placeholder_text="Search courses, lessons, and glossary…",
            fg_color=self.theme["terminal_bg"],
            border_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.search.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))
        self.search.bind("<KeyRelease>", lambda _event: self.refresh())
        ctk.CTkButton(
            header, text="Manage Educational Addons",
            command=self.open_addons,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"],
        ).grid(row=1, column=1, padx=8, pady=(2, 8))
        self.recommendation = ctk.CTkLabel(
            self, text="", text_color=self.theme["gold"],
            anchor="w", justify="left", wraplength=1080,
        )
        self.recommendation.grid(
            row=1, column=0, sticky="ew", padx=14, pady=(2, 4)
        )

    def _build_tabs(self):
        self.tabs = ctk.CTkTabview(
            self, fg_color=self.theme["panel"], border_width=1,
            border_color=self.theme["border"],
            segmented_button_fg_color=self.theme["panel_alt"],
            segmented_button_selected_color=self.theme["red"],
            segmented_button_selected_hover_color=self.theme["red_hover"],
            segmented_button_unselected_color=self.theme["panel_alt"],
            segmented_button_unselected_hover_color=self.theme["gold_dark"],
            text_color=self.theme["text"],
        )
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
        self.course_tab = self.tabs.add("Courses")
        self.glossary_tab = self.tabs.add("Glossary")
        self.bookmark_tab = self.tabs.add("Bookmarks")
        for tab in (self.course_tab, self.glossary_tab, self.bookmark_tab):
            tab.configure(fg_color=self.theme["bg"])
            tab.grid_rowconfigure(0, weight=1)
        self.course_tab.grid_columnconfigure(2, weight=1)
        self.glossary_tab.grid_columnconfigure(1, weight=1)
        self.bookmark_tab.grid_columnconfigure(1, weight=1)
        self.addon_list = self._list(self.course_tab, 230)
        self.addon_list.grid(row=0, column=0, sticky="ns", padx=(6, 3), pady=6)
        self.lesson_list = self._list(self.course_tab, 250)
        self.lesson_list.grid(row=0, column=1, sticky="ns", padx=3, pady=6)
        detail = ctk.CTkFrame(
            self.course_tab, fg_color=self.theme["panel_alt"],
            border_width=1, border_color=self.theme["border"],
        )
        detail.grid(row=0, column=2, sticky="nsew", padx=(3, 6), pady=6)
        detail.grid_rowconfigure(1, weight=1)
        detail.grid_columnconfigure(0, weight=1)
        self.lesson_heading = ctk.CTkLabel(
            detail, text="Select a course", text_color=self.theme["gold"],
            font=self.theme["header_font"], anchor="w", wraplength=570,
        )
        self.lesson_heading.grid(
            row=0, column=0, sticky="ew", padx=9, pady=(8, 3)
        )
        self.lesson_text = self._text(detail)
        self.lesson_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=5)
        actions = ctk.CTkFrame(detail, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=5, pady=6)
        for column in range(4):
            actions.grid_columnconfigure(column, weight=1)
        self.complete_button = self._button(
            actions, "Mark Complete", self.toggle_complete, 0
        )
        self.bookmark_button = self._button(
            actions, "Bookmark", self.toggle_bookmark, 1
        )
        self.practice_button = self._button(
            actions, "Record Synthetic Exercise", self.record_exercise, 2
        )
        self._button(
            actions, "Help",
            lambda: self.open_help(self.context_topic or "learning-center")
            if self.open_help else None,
            3,
        )

        self.glossary_list = self._list(self.glossary_tab, 260)
        self.glossary_list.grid(
            row=0, column=0, sticky="ns", padx=(6, 3), pady=6
        )
        self.glossary_text = self._text(self.glossary_tab)
        self.glossary_text.grid(
            row=0, column=1, sticky="nsew", padx=(3, 6), pady=6
        )
        self.bookmark_list = self._list(self.bookmark_tab, 330)
        self.bookmark_list.grid(
            row=0, column=0, sticky="ns", padx=(6, 3), pady=6
        )
        self.bookmark_text = self._text(self.bookmark_tab)
        self.bookmark_text.grid(
            row=0, column=1, sticky="nsew", padx=(3, 6), pady=6
        )

    def _list(self, parent, width):
        frame = ctk.CTkScrollableFrame(
            parent, width=width, fg_color=self.theme["panel_alt"],
            scrollbar_button_color=self.theme["gold_dark"],
            scrollbar_button_hover_color=self.theme["red_hover"],
        )
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def _text(self, parent):
        widget = ctk.CTkTextbox(
            parent, fg_color=self.theme["terminal_bg"],
            text_color=self.theme["terminal_text"], border_width=1,
            border_color=self.theme["border"], wrap="word",
        )
        widget.configure(state="disabled")
        return widget

    def _button(self, parent, text, command, column):
        button = ctk.CTkButton(
            parent, text=text, command=command,
            fg_color=self.theme["red"], hover_color=self.theme["red_hover"],
            text_color=self.theme["text"], border_width=1,
            border_color=self.theme["gold_dark"],
        )
        button.grid(row=0, column=column, sticky="ew", padx=3)
        return button

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def show_context(self, topic_id):
        self.context_topic = topic_id or ""
        topic = self.help_registry.get(topic_id) if topic_id else None
        self.recommendation.configure(
            text=(
                f"Guided recommendation for {topic.title}: review the relevant "
                "local lesson and glossary before opening a device workflow."
                if topic else
                "Guided recommendation: choose a local course or glossary term. "
                "Lesson browsing performs no device action."
            )
        )
        self.deiconify()
        self.lift()

    def refresh(self):
        if not widget_exists(self):
            return
        self.mode.configure(
            text=f"Interface mode: {self.interface_mode_provider().title()}"
        )
        query = self.search.get().strip().casefold()
        courses = {course.plugin_id: course for course in self.service.courses()}
        for child in self.addon_list.winfo_children():
            child.destroy()
        for row, addon in enumerate(self.service.educational_addons()):
            haystack = f"{addon.name} {addon.plugin_id}".casefold()
            course = courses.get(addon.plugin_id)
            lesson_match = bool(course) and any(
                query in f"{lesson.title} {lesson.explanation}".casefold()
                for lesson in course.lessons
            )
            if query and query not in haystack and not lesson_match:
                continue
            state = (
                "Loaded" if addon.loaded else "Enabled" if addon.enabled
                else "Installed" if addon.installed else "Available"
            )
            ctk.CTkButton(
                self.addon_list,
                text=f"{addon.name}\n{state} · {addon.lesson_count} lessons",
                command=lambda item=addon: self.select_addon(item),
                anchor="w", fg_color=self.theme["panel_alt"],
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"], border_width=1,
                border_color=self.theme["border"],
            ).grid(row=row, column=0, sticky="ew", padx=3, pady=3)
        self._render_glossary(query)
        self._render_bookmarks()
        if self.current_course:
            refreshed = courses.get(self.current_course.plugin_id)
            if refreshed:
                self.select_course(refreshed)
            else:
                self.current_course = None
                self.current_lesson = None
                self._render_lessons()
        self._sync_action_labels()
        self.show_context(self.context_topic)

    def select_addon(self, addon):
        course = next(
            (value for value in self.service.courses()
             if value.plugin_id == addon.plugin_id),
            None,
        )
        if course:
            self.select_course(course)
            return
        self.current_course = None
        self.current_lesson = None
        self._render_lessons()
        self.lesson_heading.configure(text=addon.name)
        self._set_text(
            self.lesson_text,
            "This educational addon is inactive. Installation, digest trust, "
            "enablement, and loading remain separate explicit actions in "
            "Add-ons Center.\n\nLesson browsing cannot activate it.",
        )

    def select_course(self, course):
        self.current_course = course
        if self.current_lesson not in course.lessons:
            self.current_lesson = course.lessons[0]
        self._render_lessons()
        self.select_lesson(self.current_lesson)

    def _render_lessons(self):
        for child in self.lesson_list.winfo_children():
            child.destroy()
        if not self.current_course:
            return
        progress = self.service.course_progress(self.current_course.course_id)
        query = self.search.get().strip().casefold()
        row = 0
        for lesson in self.current_course.lessons:
            if query and query not in (
                f"{lesson.title} {lesson.explanation}".casefold()
            ):
                continue
            markers = (
                "✓ " if lesson.lesson_id in progress.completed else ""
            ) + ("★ " if lesson.lesson_id in progress.bookmarks else "")
            ctk.CTkButton(
                self.lesson_list, text=markers + lesson.title,
                command=lambda item=lesson: self.select_lesson(item),
                anchor="w",
                fg_color=(
                    self.theme["red"] if lesson is self.current_lesson
                    else self.theme["panel_alt"]
                ),
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"], border_width=1,
                border_color=self.theme["border"],
            ).grid(row=row, column=0, sticky="ew", padx=3, pady=3)
            row += 1

    def select_lesson(self, lesson):
        self.current_lesson = lesson
        self.lesson_heading.configure(text=lesson.title)
        sections = (
            ("Explanation", (lesson.explanation,)),
            ("Prerequisites", lesson.prerequisites),
            ("Safe Synthetic Example", (lesson.synthetic_example,)),
            ("Optional Harmless Practice", (lesson.optional_practice,)),
            ("Expected Result", (lesson.expected_result,)),
            ("Hints", lesson.hints),
            ("Validation", (lesson.validation,)),
        )
        text = ""
        for title, values in sections:
            text += title + "\n" + "\n".join(
                f"• {value}" for value in values
            ) + "\n\n"
        text += (
            "This lesson cannot select a target, contact a device, open a "
            "terminal, launch Frida or Objection, or load a script."
        )
        self._set_text(self.lesson_text, text)
        self._render_lessons()
        self._sync_action_labels()

    def _sync_action_labels(self):
        if not self.current_course or not self.current_lesson:
            state = "disabled"
            complete = "Mark Complete"
            bookmark = "Bookmark"
        else:
            state = "normal"
            progress = self.service.course_progress(
                self.current_course.course_id
            )
            complete = (
                "Mark Incomplete" if self.current_lesson.lesson_id
                in progress.completed else "Mark Complete"
            )
            bookmark = (
                "Remove Bookmark" if self.current_lesson.lesson_id
                in progress.bookmarks else "Bookmark"
            )
        self.complete_button.configure(state=state, text=complete)
        self.bookmark_button.configure(state=state, text=bookmark)
        self.practice_button.configure(state=state)

    def toggle_complete(self):
        progress = self.service.course_progress(self.current_course.course_id)
        current = self.current_lesson.lesson_id in progress.completed
        self.service.mark_complete(
            self.current_course, self.current_lesson, not current
        )
        self._render_lessons()
        self._sync_action_labels()

    def toggle_bookmark(self):
        progress = self.service.course_progress(self.current_course.course_id)
        current = self.current_lesson.lesson_id in progress.bookmarks
        self.service.bookmark(
            self.current_course, self.current_lesson, not current
        )
        self._render_lessons()
        self._render_bookmarks()
        self._sync_action_labels()

    def record_exercise(self):
        self.service.record_exercise(
            self.current_course, self.current_lesson
        )
        self._sync_action_labels()

    def _render_glossary(self, query):
        for child in self.glossary_list.winfo_children():
            child.destroy()
        entries = self.help_registry.search_glossary(query)
        for row, entry in enumerate(entries):
            ctk.CTkButton(
                self.glossary_list, text=entry.term,
                command=lambda item=entry: self._show_glossary(item),
                anchor="w", fg_color=self.theme["panel_alt"],
                hover_color=self.theme["red_hover"],
                text_color=self.theme["text"], border_width=1,
                border_color=self.theme["border"],
            ).grid(row=row, column=0, sticky="ew", padx=3, pady=3)
        if entries:
            self._show_glossary(entries[0])
        else:
            self._set_text(self.glossary_text, "No matching glossary entries.")

    def _show_glossary(self, entry):
        self._set_text(
            self.glossary_text,
            f"{entry.term}\n{'=' * len(entry.term)}\n\n"
            f"{entry.definition}\n\nRelated: "
            f"{', '.join(entry.related_terms) or 'None'}",
        )

    def _render_bookmarks(self):
        for child in self.bookmark_list.winfo_children():
            child.destroy()
        row = 0
        for course in self.service.courses():
            progress = self.service.course_progress(course.course_id)
            for lesson in course.lessons:
                if lesson.lesson_id not in progress.bookmarks:
                    continue
                ctk.CTkButton(
                    self.bookmark_list,
                    text=f"{course.title}\n{lesson.title}",
                    command=lambda c=course, item=lesson: self._open_bookmark(c, item),
                    anchor="w", fg_color=self.theme["panel_alt"],
                    hover_color=self.theme["red_hover"],
                    text_color=self.theme["text"], border_width=1,
                    border_color=self.theme["border"],
                ).grid(row=row, column=0, sticky="ew", padx=3, pady=3)
                row += 1
        if not row:
            ctk.CTkLabel(
                self.bookmark_list, text="No bookmarked lessons.",
                text_color=self.theme["muted"],
            ).grid(row=0, column=0, padx=8, pady=16)
        self._set_text(
            self.bookmark_text,
            "Bookmarks are stored only in the local Learning Center progress file.",
        )

    def _open_bookmark(self, course, lesson):
        self.tabs.set("Courses")
        self.select_course(course)
        self.select_lesson(lesson)

    def close(self):
        if self.unsubscribe:
            self.unsubscribe()
            self.unsubscribe = None
        self.callbacks.cancel_all()
        if self.on_close:
            self.on_close()
        self.destroy()
