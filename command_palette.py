import customtkinter
import tkinter as tk
from tkinter import filedialog
import commands
import webbrowser
import subprocess
import json
import os
import re
from thefuzz import process, fuzz

customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("blue")

class ManageVarsWindow(customtkinter.CTkToplevel):
    def __init__(self, master, var_list, existing_vars, callback):
        super().__init__(master)
        self.master_app = master
        self.geometry("400x300")
        self.transient(self.master_app)
        self.attributes("-topmost", True)
        self.focus()

        self.var_list = var_list
        self.callback = callback
        self.entry_widgets = {}

        self.grid_columnconfigure(1, weight=1)

        self.scrollable_frame = customtkinter.CTkScrollableFrame(self)
        self.scrollable_frame.grid(column=0, row=0, sticky="nsew", columnspan=2, padx=10, pady=10)
        self.grid_rowconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(
            self.scrollable_frame,
            text="Set default values for variables:",
            font=customtkinter.CTkFont(family="Helvetica", size=12),
        ).grid(column=0, row=0, sticky="w", pady=(0, 10), columnspan=2)

        for i, var_name in enumerate(var_list, start=1):
            label = customtkinter.CTkLabel(self.scrollable_frame, text=f"{var_name}: ")
            label.grid(column=0, row=i, sticky="w", pady=5, padx=10)

            entry = customtkinter.CTkEntry(self.scrollable_frame)
            entry.grid(column=1, row=i, sticky="ew", pady=5, padx=10)
            self.entry_widgets[var_name] = entry
            if var_name in existing_vars:
                entry.insert(0, existing_vars[var_name])

        self.save_button = customtkinter.CTkButton(self, text="Save Defaults", command=self.save_and_close)
        self.save_button.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

    def save_and_close(self):
        new_vars_dict = {}
        for var_name, entry_widget in self.entry_widgets.items():
            new_vars_dict[var_name] = entry_widget.get().strip()

        self.callback(new_vars_dict)
        self.destroy()

class ConfirmationWindow(customtkinter.CTkToplevel):
    def __init__(self, master, title, message, callback):
        customtkinter.CTkToplevel.__init__(self, master)
        self.geometry("350x150")
        self.title(title)
        self.transient(master)
        self.attributes("-topmost", True)

        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(0, weight=1)

        customtkinter.CTkLabel(self, text=message, wraplength=300).grid(row=0, column=0, sticky="nsew", columnspan=2, padx=20, pady=(15, 10))
        customtkinter.CTkButton(
            self,
            text="Cancel",
            command=self.destroy,
            fg_color="gray",
            hover_color="#555555"
        ).grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        customtkinter.CTkButton(
            self,
            text="Confirm",
            command=lambda: self._confirm_and_call(callback),
            fg_color="#A51F1F",
            hover_color="#801818"
        ).grid(row=1, column=1, sticky="ew", padx=20, pady=10)

    def _confirm_and_call(self, callback):
        callback()
        self.destroy()

class CTkinterApplication(customtkinter.CTk):

    def __init__(self):
        super().__init__()
        self.default_commands = []
        self.result_widgets = []
        self.custom_command_file = "custom_commands.json"

        self.geometry("600x400")
        self.resizable(width=False, height=False)
        self.title("Command Palette")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.history_file = "command_history.json"
        self.command_history = []
        self.load_history()

        self.color_theme = "blue"
        self.appearance_mode = "Dark"
        self.fuzzy_threshold = 60
        self.new_commands = []
        self.commands = commands.commands
        self.settings_window = None
        self.load_command()
        self.selected_index = 0
        self.filtered_commands = self.commands

        self.expanded_row_index = -1
        self.expanded_frame = None

        self.search_entry = customtkinter.CTkEntry(
            self,
            placeholder_text="Search for commands(for example: youtube, shutdown pc, open ...)",
            font=customtkinter.CTkFont(size=14, family="Lexend"),
            width=580,
            height=40,
            corner_radius=10,
            border_width=2,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        self.search_entry.bind("<KeyRelease>", self.filter_query)
        self.search_entry.bind("<Up>", self.move_selection)
        self.search_entry.bind("<Down>", self.move_selection)
        self.search_entry.bind("<Return>", self.handle_return_key)
        self.search_entry.bind("<Shift-Return>", self.handle_return_key)

        self.result_frame = customtkinter.CTkScrollableFrame(
            self,
            corner_radius=15,
            fg_color="transparent",
            label_text="Available commands",
            label_font=customtkinter.CTkFont(size=10, weight="bold"),
        )
        self.result_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.result_frame.grid_columnconfigure(0, weight=1)

        self.last_command = customtkinter.CTkLabel(
            self,
            text="Your last command will show here",
            font=customtkinter.CTkFont(size=11, family="Lexend"),
        )
        self.last_command.grid(row=2, column=0, sticky="ew", padx=10, pady=10)

        self.filter_query(None)
        self.render_results(self.commands, self.command_history)
        self.update_selection_visual()
        self.after(1200, lambda : self.search_entry.focus())

    def handle_return_key(self, event):
        is_shift_pressed = (event.state & 0x0001) != 0
        if not self.result_widgets or self.selected_index >= len(self.filtered_commands):
            return
        command_tuple = self.filtered_commands[self.selected_index]
        if is_shift_pressed:
            print(f"Shift+Enter detected for: {command_tuple}")
            self.toggle_argument_expansion(command_tuple, self.selected_index)
        else:
            print(f"Enter detected for: {command_tuple}")
            self.execute_selected_command()

    def update_selection_visual(self):
        for i, row in enumerate(self.result_widgets):
            if i == self.selected_index:
                row.configure(border_width=2, border_color="#1F6AA5")
            else:
                row.configure(border_width=0)

    def move_selection(self, event):
        max_selection = len(self.result_widgets)-1
        new_selection = self.selected_index

        if event.keysym == "Up":
            new_selection = self.selected_index - 1
            if new_selection < 0:
                new_selection = max_selection
        elif event.keysym == "Down":
            new_selection = (self.selected_index + 1) % (max_selection+1)

        self.selected_index = new_selection
        self.update_selection_visual()

        selected_row = self.result_widgets[self.selected_index]
        canvas = self.result_frame._parent_canvas

        bbox = canvas.bbox("all")
        if bbox is None:
            return "break"

        total_content_height = bbox[3]
        if total_content_height == 0:
            return "break"

        y_pos = selected_row.winfo_y()
        row_height = selected_row.winfo_height()

        top_frac = y_pos / total_content_height
        bottom_frac = (y_pos + row_height) / total_content_height

        view_fracs = canvas.yview()
        view_top_frac = view_fracs[0]
        view_bottom_frac = view_fracs[1]

        if top_frac < view_top_frac:
            canvas.yview_moveto(top_frac)

        elif bottom_frac > view_bottom_frac:
            scroll_amount = bottom_frac - view_bottom_frac
            canvas.yview_moveto(view_top_frac + scroll_amount)
        print(self.selected_index)

    def render_results(self, result=None, history=None):
        self.clear_results()
        idx = 0
        if history and not self.search_entry.get():
            customtkinter.CTkLabel(
                self.result_frame,
                text="RECENT COMMANDS ",
                font=customtkinter.CTkFont(size=14, weight="bold", slant="italic"),
                text_color="#B0B0B0"
            ).grid(row=idx, column=0, sticky="w", padx=5, pady=(0, 5))
            idx += 1

            for i, command_tuple in enumerate(history):
                name, desc, action, target, origin, target_vars = command_tuple
                self.create_result_row(name, desc, action, target, origin, target_vars, idx, is_history=True)
                idx += 1

        customtkinter.CTkLabel(
            self.result_frame,
            text="ALL AVAILABLE COMMANDS ",
            font=customtkinter.CTkFont(size=10, weight="bold", slant="italic"),
            text_color="#B0B0B0"
        ).grid(row=idx, column=0, sticky="w", padx=5, pady=(15, 0))
        idx += 1
        self.selected_index = 0
        self.update_selection_visual()

        if result:
            history_4tuples = [cmd[:4] for cmd in self.command_history]
            for i, command_tuple in enumerate(result):
                name, description, action, target, origin, target_vars = command_tuple
                if history and not self.search_entry.get():
                    command_4tuple = (name, description, action, target)
                    if command_4tuple in history_4tuples:
                        continue
                self.create_result_row(name, description, action, target, origin, target_vars, idx+i)
        self.result_frame._parent_canvas.yview_moveto(0.0)

    def clear_results(self):
        for widget in self.result_widgets:
            widget.destroy()
        self.result_widgets = []
        self.expanded_frame = None
        self.expanded_row_index = -1
        for widget in self.result_frame.winfo_children():
            widget.destroy()

    def create_result_row(self, name, description, action, target, origin, target_vars, idx, is_history=False):
        full_command_tuple = (name, description, action, target, origin, target_vars)
        left_click_handler = lambda e, cmd=full_command_tuple : self.execute_command(cmd)
        right_click_handler = lambda e, cmd=full_command_tuple : self.show_context_menu(e, cmd)
        shift_click_handler = lambda e, cmd=full_command_tuple, row_idx=len(self.result_widgets) : self.toggle_argument_expansion(cmd, row_idx)
        if self.appearance_mode == "Dark":
            result_row_color = "#2A2A2A" if idx % 2 == 0 else "#252525"
            if is_history:
                result_row_color = "#353535" if idx % 2 == 0 else "#3A3A3A"
        else:
            result_row_color = "#F2F2F2" if idx % 2 == 0 else "#FAFAFA"
            if is_history:
                result_row_color = "#DCDCDC" if idx % 2 == 0 else "#D2D2D2"

        result_row = customtkinter.CTkFrame(
            self.result_frame,
            corner_radius=8,
            fg_color=result_row_color,
            height=40
        )
        result_row.command_data = full_command_tuple[:4]
        result_row.grid_columnconfigure(1, weight=1)
        result_row.grid_rowconfigure(0, weight=1)
        result_row.grid(row=idx, column=0, sticky="ew", padx=5, pady=3)
        result_row.bind("<Shift-Button-1>", shift_click_handler)
        result_row.bind("<Button-1>", left_click_handler)
        result_row.bind("<Button-3>", right_click_handler)
        name_text = f"🕒 {name}" if is_history else name

        name_label = customtkinter.CTkLabel(
            result_row,
            text=name_text,
            font=customtkinter.CTkFont(size=13, weight="bold"),
            anchor="w",
            text_color="#10B981" if is_history else "white" if self.appearance_mode == "Dark" else "black",
        )
        name_label.grid(row=0, column=0, sticky="w", padx=(10, 0), pady=5)
        name_label.bind("<Shift-Button-1>", shift_click_handler)
        name_label.bind("<Button-1>", left_click_handler)
        name_label.bind("<Button-3>", right_click_handler)
        desc_text = description
        if target_vars and len(target_vars) > 0:
            var_len = len(target_vars)
            desc_text = f"{description} - {var_len} var{'s' if var_len > 1 else ''}"

        description_label = customtkinter.CTkLabel(
            result_row,
            text=desc_text,
            font=customtkinter.CTkFont(size=12),
            anchor="e",
            text_color="#888888"
        )
        description_label.grid(row=0, column=1, sticky="ew", padx=10, pady=5)
        description_label.bind("<Shift-Button-1>", shift_click_handler)
        description_label.bind("<Button-1>", left_click_handler)
        description_label.bind("<Button-3>", right_click_handler)

        if origin=="CUSTOM" and not is_history:
            origin_label = customtkinter.CTkLabel(
                result_row,
                text="CUSTOM",
                font=customtkinter.CTkFont(size=10, family="Lexend", weight="bold"),
                anchor="center",
                text_color="#FACC15",
                bg_color="#453A1B",
                corner_radius=5,
            )
            origin_label.grid(row=0, column=2, sticky="e", padx=(0, 5), pady=5)
            origin_label.bind("<Shift-Button-1>", shift_click_handler)
            origin_label.bind("<Button-1>", left_click_handler)
            origin_label.bind("<Button-3>", right_click_handler)

        if is_history:
            pass
        else:
            action_label = customtkinter.CTkLabel(
                result_row,
                text=action,
                font=customtkinter.CTkFont(family="Lexend", size=10),
                anchor="e",
                text_color="white",
                bg_color="#666666",
                corner_radius=5,
            )
            action_label.grid(row=0, column=3, sticky="e", padx=(0, 10), pady=5)
            action_label.bind("<Shift-Button-1>", shift_click_handler)
            action_label.bind("<Button-1>", left_click_handler)
            action_label.bind("<Button-3>", right_click_handler)

        self.result_widgets.append(result_row)

    def toggle_argument_expansion(self, command_tuple, row_index):
        if self.expanded_frame:
            self.expanded_frame.destroy()
            self.expanded_frame = None
            prev_index = self.expanded_row_index
            self.expanded_row_index = -1
            self.search_entry.focus()
            if prev_index == row_index:
                return

        name, desc, action, target, origin, target_vars = command_tuple
        print(origin)

        if not target_vars:
            print("no target variables found")
            return

        self.expanded_row_index = row_index
        target_row = self.result_widgets[self.selected_index]
        self.expanded_frame = customtkinter.CTkFrame(target_row, fg_color="transparent")
        self.expanded_frame.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 5))
        self.expanded_frame.entries = {}

        for i, (var_name, default_value) in enumerate(target_vars.items()):
            label = customtkinter.CTkLabel(
                self.expanded_frame,
                text=f"{var_name}: ",
                font=customtkinter.CTkFont(weight="bold", size=11),
                text_color="gray"
            )
            label.grid(row=i, column=0, sticky="w", padx=(5, 5), pady=2)
            if origin != "HISTORY":
                entry = customtkinter.CTkEntry(
                    self.expanded_frame,
                    height=25,
                    placeholder_text=default_value,
                )
                entry.insert(0, default_value)
                entry.grid(row=i, column=1, sticky="ew", padx=(0, 5), pady=2)
                entry.bind("<Return>", lambda e, cmd=command_tuple: self.execute_expanded_command(cmd))
                entry.bind("<Shift-Return>",
                           lambda e, cmd=command_tuple, idx=row_index: self.toggle_argument_expansion(cmd, idx))

                self.expanded_frame.entries[var_name] = entry
                if i == 0: entry.focus()
            else:
                customtkinter.CTkLabel(
                    self.expanded_frame,
                    text=default_value,
                ).grid(row=i, column=1, sticky="w", padx=(0, 5), pady=2)

        self.expanded_frame.columnconfigure(1, weight=1)

    def execute_expanded_command(self, command_tuple):
        if not self.expanded_frame:
            return

        args = {}
        for var_name, entry in self.expanded_frame.entries.items():
            args[var_name] = entry.get()

        name, desc, action, target, origin, target_vars = command_tuple
        
        try:
            final_target = target.format(**args)
            final_command = (name, desc, action, final_target, origin, args)
            self.execute_command(final_command)
        except KeyError as e:
            self.last_command.configure(text=f"Error formatting command: {e}", text_color="red")

    def filter_query(self, event=None):
        if event is not None:
            if event.keysym in ['Up', 'Down', 'Return', 'Shift_L', 'Shift_R']:
                return
        query = self.search_entry.get().lower()
        self.filtered_commands = []
        if not query:
            self.filtered_commands = self.command_history + [cmd for cmd in self.commands if cmd[:4] not in [cmmd[:4] for cmmd in self.command_history]]
            self.result_frame.configure(label_text="Command History & All Commands")
            self.render_results(self.commands, self.command_history)
            self.selected_index = 0
            self.update_selection_visual()
            return
        else:
            results = process.extract(
                query,
                [name.lower() for name, _, _, _, _, _ in self.commands],
                scorer=fuzz.partial_ratio,
                limit=12
            )
            names = [name for name, score in results if score >= self.fuzzy_threshold]

            for name in names:
                index = [name.lower() for name, _, _, _, _, _ in self.commands].index(name)
                if self.commands[index] not in self.filtered_commands:
                    self.filtered_commands.append(self.commands[index])
                else:
                    index = [name.lower() for name, _, _, _, _, _ in self.commands].index(name, index+1)
                    self.filtered_commands.append(self.commands[index])

            self.result_frame.configure(label_text=f"Showing result for \"{query}\" ({len(self.filtered_commands)} results)")
        self.render_results(self.filtered_commands)
        self.selected_index = 0
        self.update_selection_visual()

    def show_context_menu(self, event, command):
        if command[4] != "CUSTOM":
            return
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(
            label="Edit command",
            command=lambda : self.open_edit_window(command),
        )
        self.context_menu.add_command(
            label="Delete command",
            command=lambda : self.delete_confirmation_window(command),
        )
        self.context_menu.tk_popup(event.x_root, event.y_root)
        self.context_menu.grab_release()

    def open_edit_window(self, command):
        EditCommandWindow(self, command)


    def delete_confirmation_window(self, command):
        name = command[0]
        message = f"Are you sure you want to permanently delete {name}?"

        self.message_box = ConfirmationWindow(
            self,
            title="Confirm Deletion",
            message=message,
            callback=lambda: self.delete_command(command)
        )

    def delete_command(self, command):
        self.commands = [cmd for cmd in self.commands if cmd != command]
        self.new_commands = [cmd for cmd in self.new_commands if cmd != command]
        self.save_command()
        current_query = self.search_entry.get() # get query to refresh UI
        command_4tuple = command[:4]
        self.command_history = [cmd for cmd in self.command_history if cmd != command_4tuple]
        self.save_history()
        self.filter_query(None)
        self.last_command.configure(text=f"Deleted command {command[0]}", text_color="#A51F1F")

    def execute_selected_command(self, *args):
        print(self.filtered_commands)
        command_to_execute = self.filtered_commands[self.selected_index]
        if len(command_to_execute) == 5:
            command_to_execute += ({},)
        elif len(command_to_execute) == 4:
            command_to_execute += ("BUILT-IN", {})
        self.execute_command(command_to_execute)

    def add_to_history(self, command):
        if command in self.command_history:
            self.command_history.remove(command)

        self.command_history.insert(0, command)

        max_history = 5
        self.command_history = self.command_history[:max_history]

        self.save_history()

    def execute_command(self, command):
        name, description, action, target, origin, target_vars = command
        final_target = target
        try:
            if target_vars and len(target_vars) > 0:
                default_vars = {key: value for key, value in target_vars.items()}
                final_target = target.format(**default_vars)
        except KeyError as e:
            self.last_command.configure(text=f"Error: Missing default value for {e}", text_color="red")
        if action == "WEB":
            webbrowser.open_new_tab(final_target)
        elif action == "SYSTEM":
            subprocess.run(final_target, shell=True)
        elif action == "OPEN":
            subprocess.Popen(final_target, shell=True)
        elif action == "CONSOLE":
            if final_target == "exit":
                self.destroy()
                return
            if final_target == "setting-window":
                if not hasattr(self, 'settings_window') or self.settings_window is None or self.settings_window.winfo_exists():
                    self.settings_window = SettingsWindow(self)
                self.settings_window.focus()

        self.add_to_history(command[:4] + ("HISTORY",) + command[5:])

        self.last_command.configure(text=f"Last command executed: {name}", text_color="#000000" if customtkinter.get_appearance_mode() != "Dark" else "#FFFFFF")
        self.search_entry.delete(0, "end")
        self.filter_query()
        self.result_frame.configure(label_text="Available commands")
        self.render_results(self.filtered_commands, self.command_history)
        self.selected_index = 0
        self.update_selection_visual()

    def load_history(self):
        self.command_history = []
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    loaded_list = json.load(f)
                    for cmd in loaded_list:
                        if len(cmd) == 4:
                            self.command_history.append(tuple(cmd) + ("HISTORY", {}))
                        elif len(cmd) == 5:
                            self.command_history.append(tuple(cmd) + ({},))
                        elif len(cmd) == 6:
                            self.command_history.append(tuple(cmd))
            except (FileNotFoundError, json.JSONDecodeError, IndexError):
                print("Error loading command history file. Starting with an empty list.")
                self.command_history = []

    def save_history(self):
        try:
            with open(self.history_file, "w") as f:
                json.dump([list(cmd) for cmd in self.command_history], f, indent=4)
        except Exception as e:
            print(f"An error occurred while saving the command history file: {e}")

    # Load and save custom commands
    def load_command(self):
        self.new_commands = []
        self.default_commands = [(cmd[0], cmd[1], cmd[2], cmd[3], "BUILT-IN", {}) for cmd in self.commands]
        self.commands = self.default_commands
        self.filtered_commands = self.commands
        if os.path.exists(self.custom_command_file):
            try:
                with open(self.custom_command_file, "r") as f:
                    for cmd in json.load(f):
                        if len(cmd) == 5:
                            self.new_commands.append(tuple(cmd) + ({},))
                        elif len(cmd) == 4:
                            self.new_commands.append(tuple(cmd) + ("CUSTOM", {}))
                        elif len(cmd) == 6:
                            self.new_commands.append(tuple(cmd))
                self.commands += self.new_commands
                self.filtered_commands = self.commands
            except FileNotFoundError:
                print("Error opening custom commands file")

    def save_command(self):
        try:
            with open(self.custom_command_file, "w") as f:
                json.dump([list(cmd) for cmd in self.new_commands], f, indent=4)
        except:
            print("An error occurred while saving the custom commands file")

    def export_commands(self):
        self.file_path = filedialog.asksaveasfilename(
            title="Export Commands",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if not self.file_path:
            self.last_command.configure(text="Export cancelled", text_color="orange")
            return

        try:
            export_data = [cmd[:4] for cmd in self.new_commands]
            with open(self.file_path, "w") as f:
                json.dump(export_data, f, indent=4)
                self.last_command.configure(text="Export successful", text_color="green")
        except:
            self.last_command.configure(text="Export unsuccessful", text_color="red")

    def import_commands(self):
        self.file_path = filedialog.askopenfilename(
            title="Import Commands",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
        )
        if not self.file_path:
            self.last_command.configure(text="Import cancelled", text_color="orange")
            return

        try:
            with open(self.file_path, "r") as f:
                import_data = json.load(f)
        except:
            self.last_command.configure(text="Import unsuccessful", text_color="red")
            return

        if not isinstance(import_data, list):
            self.last_command.configure(text="File data does not seem to be in a list form", text_color="red")
            return
        current_names = [cmd[0] for cmd in self.commands]
        imported_count, skipped_count = 0, 0

        for cmd_data in import_data:
            if isinstance(cmd_data, list) and (len(cmd_data) == 4 or len(cmd_data) == 5):
                name = cmd_data[0]
                if name in current_names:
                    skipped_count += 1
                    continue

                if len(cmd_data) == 4:
                    new_command_tuple = tuple(cmd_data) + ("CUSTOM",)
                else:
                    new_command_tuple = tuple(cmd_data[:4]) + ("CUSTOM",)

                self.new_commands.append(new_command_tuple)
                current_names.append(name)
                imported_count += 1
            else:
                skipped_count += 1

        if imported_count > 0:
            self.save_command()
            self.load_command()
            self.filter_query(None)
            self.last_command.configure(
                text=f"Import successful! Added {imported_count} new commands. Skipped {skipped_count} invalid/duplicate commands.",
                text_color="green")
        else:
            self.last_command.configure(text=f"No new commands were imported. Skipped {skipped_count} commands.", text_color="orange")

class SettingsWindow(customtkinter.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.master_app = master
        self.title("Settings and Custom Commands")
        self.geometry("650x450")
        self.transient(master)
        self.columnconfigure((0, 1), weight=1)
        self.rowconfigure(0, weight=1)
        self.focus()

        self.temp_target_vars = {}

        self.appearance_frame = customtkinter.CTkFrame(self, corner_radius=10)
        self.appearance_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.appearance_frame.columnconfigure(0, weight=1)

        # Appearance Settings code

        customtkinter.CTkLabel(
            self.appearance_frame,
            text="General Settings",
            font=customtkinter.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="n", padx=20, pady=(10, 5))

        customtkinter.CTkLabel(
            self.appearance_frame,
            text="Appearance Mode:"
        ).grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.appearance_mode_option_menu = customtkinter.CTkOptionMenu(
            self.appearance_frame,
            values=['System', 'Light', 'Dark'],
            command=self.change_appearance_mode,
            width=200
        )
        self.appearance_mode_option_menu.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.appearance_mode_option_menu.set(customtkinter.get_appearance_mode())

        customtkinter.CTkLabel(
            self.appearance_frame,
            text="Color Theme:"
        ).grid(row=3, column=0, sticky="w", padx=20, pady=(10, 0))
        self.color_theme_option_menu = customtkinter.CTkOptionMenu(
            self.appearance_frame,
            values=['Blue', 'Green', 'Dark-blue'],
            command=self.change_color_theme,
            width=200
        )
        self.color_theme_option_menu.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.color_theme_option_menu.set(self.master_app.color_theme)

        customtkinter.CTkLabel(
            self.appearance_frame,
            text="Search relate score(1-100):"
        ).grid(row=5, column=0, sticky="w", padx=20, pady=(0, 10))

        self.threshold_label = customtkinter.CTkLabel(
            self.appearance_frame,
            text=f"score: {self.master_app.fuzzy_threshold}",
            font=customtkinter.CTkFont(size=10, weight="bold")
        )
        self.threshold_label.grid(row=6, column=0, sticky="w", padx=20, pady=(0, 10))

        self.threshold_slider = customtkinter.CTkSlider(
            self.appearance_frame,
            from_=1,
            to=100,
            number_of_steps=99,
            command=self.change_threshold_slider,
            width=200
        )
        self.threshold_slider.set(self.master_app.fuzzy_threshold)
        self.threshold_slider.grid(row=7, column=0, sticky="ew", padx=20, pady=(0, 10))

        #Import/export settings
        customtkinter.CTkLabel(
            self.appearance_frame,
            text="Imports / Exports:",
            font=customtkinter.CTkFont(size=12, weight="bold")
        ).grid(row=8, column=0, sticky="w", padx=20, pady=(0, 10))

        customtkinter.CTkButton(
            self.appearance_frame,
            text="Import",
            command=self.master_app.import_commands,
            corner_radius=5
        ).grid(row=9, column=0, sticky="ew", padx=20, pady=(0, 10))

        customtkinter.CTkButton(
            self.appearance_frame,
            text="Export",
            command=self.master_app.export_commands,
            corner_radius=5
        ).grid(row=10, column=0, sticky="ew", padx=20, pady=(0, 10))

        # Adding new Command settings
        self.add_command_frame = customtkinter.CTkFrame(
            self,
            corner_radius=10,
        )
        self.add_command_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.add_command_frame.columnconfigure(0, weight=1)

        customtkinter.CTkLabel(
            self.add_command_frame,
            text="Add New Commands",
            font=customtkinter.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, sticky="n", padx=20, pady=(10, 5))


        # command name
        customtkinter.CTkLabel(self.add_command_frame, text="Add command name:").grid(row=1, column=0, sticky="w", padx=20, pady=(5, 0))
        self.name_entry = customtkinter.CTkEntry(
            self.add_command_frame,
            placeholder_text="Name of the Command(for example: Google, WhatsApp)...",
            width=250,
        )
        self.name_entry.grid(row=2, column=0, sticky="ew", padx=20, pady=(0,5))

        # command description
        customtkinter.CTkLabel(self.add_command_frame, text="Add command description:").grid(row=3, column=0, sticky="w", padx=20, pady=(5, 0))
        self.description_entry = customtkinter.CTkEntry(
            self.add_command_frame,
            placeholder_text="Describe what your command will do...",
            width=250,
        )
        self.description_entry.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 5))

        # action type of command
        customtkinter.CTkLabel(self.add_command_frame, text="Action Type:").grid(row=5, column=0, sticky="w", padx=20, pady=(5, 0))
        self.action_type_option_menu = customtkinter.CTkOptionMenu(
            self.add_command_frame,
            values=["WEB", "SYSTEM", "OPEN"]
        )
        self.action_type_option_menu.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 5))
        self.action_type_option_menu.set("WEB")

        # command's target
        customtkinter.CTkLabel(self.add_command_frame, text="Target - absolute (Use {var_name} for variables):").grid(row=7, column=0, sticky="w", padx=20, pady=(5, 0))
        self.target_frame = customtkinter.CTkFrame(self.add_command_frame, fg_color='transparent')
        self.target_frame.grid(row=8, column=0, sticky="ew", padx=20, pady=(0, 10))
        self.target_frame.columnconfigure(0, weight=1)
        self.target_frame.columnconfigure(1, weight=0)

        self.target_entry = customtkinter.CTkEntry(
            self.target_frame,
            placeholder_text="e.g. https://www.xyz-site.com/{var_name} for WEB or calc.exe for OPEN",
            width=250,
        )
        self.target_entry.grid(row=0, column=0, sticky="ew", padx=20, pady=(0, 15))
        self.target_entry.bind("<KeyRelease>", self.check_target_for_vars)

        self.manage_vars_button = customtkinter.CTkButton(
            self.target_frame,
            text="Manage Variables",
            width=80,
            command=self.open_manage_vars_window,
        )

        self.check_target_for_vars()
        # add button
        self.add_button = customtkinter.CTkButton(
            self.add_command_frame,
            text="Add Command",
            command=self.add_command,
            hover_color="#185280"
        )
        self.add_button.grid(row=9, column=0, sticky="ew", padx=20, pady=(0, 10))

        # reset button
        self.reset_button = customtkinter.CTkButton(
            self.add_command_frame,
            text="Reset Entries",
            command=self.reset_command_entry,
            hover_color="#185280"
        )
        self.reset_button.grid(row=10, column=0, sticky="ew", padx=20, pady=(0, 10))

        # status for acceptance for command
        self.status_label = customtkinter.CTkLabel(self.add_command_frame, text="", text_color="red")
        self.status_label.grid(row=11, column=0, sticky="ew", padx=20, pady=(5, 10))

    def check_target_for_vars(self, event=None):
        target_text = self.target_entry.get()
        variables = set(re.findall(r'\{([^}]+)\}', target_text))
        if variables:
            self.manage_vars_button.grid(row=0, column=1, sticky="w", padx=20, pady=(0, 15))
        else:
            self.manage_vars_button.grid_forget()
            self.temp_target_vars = {}

    def open_manage_vars_window(self):
        target_text = self.target_entry.get()
        variables = sorted(list(set(re.findall(r'\{([^}]+)\}', target_text))))

        if not variables:
            return

        ManageVarsWindow(
            self,
            var_list=variables,
            existing_vars=self.temp_target_vars,
            callback=self.update_temp_vars,
        )

    def update_temp_vars(self, new_vars_dict):
        self.temp_target_vars = new_vars_dict

    def change_threshold_slider(self, value):
        value = int(value)
        self.master_app.fuzzy_threshold = value
        self.threshold_label.configure(text=f"score: {value}")

    def close_window(self):
        self.destroy()
        self.master_app.settings_window = None

    def change_appearance_mode(self, mode : str):
        customtkinter.set_appearance_mode(mode)
        self.master_app.last_command.configure(text_color="#000000" if mode.lower() != "dark" else "#FFFFFF")
        self.master_app.filter_query()
        self.master_app.appearance_mode = mode
        self.master_app.render_results(self.master_app.filtered_commands, self.master_app.command_history)

    def change_color_theme(self, color : str):
        customtkinter.set_default_color_theme(color.lower())
        self.master_app.color_theme = color
        self.master_app.render_results(self.master_app.filtered_commands, self.master_app.command_history)

    def reset_command_entry(self):
        self.name_entry.delete(0, "end")
        self.description_entry.delete(0, "end")
        self.target_entry.delete(0, "end")
        self.action_type_option_menu.set("WEB")
        self.temp_target_vars = {}
        self.check_target_for_vars()

    def add_command(self):
        name = self.name_entry.get().strip()
        description = self.description_entry.get().strip()
        action_type = self.action_type_option_menu.get().strip()
        target = self.target_entry.get().strip()
        temp_target_vars = self.temp_target_vars

        if not (name and target):
            self.status_label.configure(text="Name and Target cannot be left blank")
            return

        if name in [cmd[0] for cmd in self.master_app.commands]:
            self.status_label.configure(text=f"Command '{name}' already exists")
            return

        new_command = (name, description if description else "User's Custom Command", action_type, target, "CUSTOM", temp_target_vars)
        self.master_app.commands.append(new_command)
        self.master_app.new_commands.append(new_command)

        self.master_app.save_command()
        self.master_app.render_results(self.master_app.commands, self.master_app.command_history)

        self.reset_command_entry()
        self.status_label.configure(text=f"Command '{name}' was successfully added", text_color="green")

class EditCommandWindow(customtkinter.CTkToplevel):
    def __init__(self, master, original_command):
        super().__init__(master)
        self.original_command = original_command
        self.old_name, self.old_description, self.old_action_type, self.old_target, self.old_origin, self.old_target_vars = self.original_command
        self.master_app = master
        self.geometry("450x500")
        self.transient(master)
        self.title(f"Edit Command Window | Edit Command : {self.old_name}")
        self.attributes("-topmost", True)
        self.focus()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.temp_target_vars = {}

        customtkinter.CTkLabel(self, text=f"Edit Command Window | {self.old_name} | {self.old_action_type}", font=customtkinter.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="n", padx=20, pady=10
        )

        customtkinter.CTkLabel(
            self,
            text="New name:",
            font=customtkinter.CTkFont(size=12, family="Lexend")
        ).grid(row=1, column=0, sticky="w", padx=20)
        self.new_name_entry = customtkinter.CTkEntry(
            self,
            placeholder_text=self.old_name,
            corner_radius=10,
            width=250,
        )
        self.new_name_entry.grid(row=2, column=0, sticky="ew", padx=20, pady=5)

        customtkinter.CTkLabel(
            self,
            text="New description:",
            font=customtkinter.CTkFont(size=12, family="Lexend")
        ).grid(row=3, column=0, sticky="w", padx=20)
        self.new_desc_entry = customtkinter.CTkEntry(
            self,
            placeholder_text=self.old_description,
            corner_radius=10,
            width=250,
        )
        self.new_desc_entry.grid(row=4, column=0, sticky="ew", padx=20, pady=5)

        customtkinter.CTkLabel(
            self,
            text="New action type:",
            font=customtkinter.CTkFont(size=12, family="Lexend")
        ).grid(row=5, column=0, sticky="w", padx=20)
        self.new_action_type_option_menu = customtkinter.CTkOptionMenu(
            self,
            values=["WEB", "SYSTEM", "OPEN"],
            corner_radius=10,
            width=250,
        )
        self.new_action_type_option_menu.grid(row=6, column=0, sticky="ew", padx=20, pady=5)
        self.new_action_type_option_menu.set("WEB")

        customtkinter.CTkLabel(
            self,
            text="New target - PATH or URL:",
            font=customtkinter.CTkFont(size=12, family="Lexend")
        ).grid(row=7, column=0, sticky="w", padx=20)
        self.target_frame = customtkinter.CTkFrame(
            self
        )
        self.target_frame.grid(row=8, column=0, sticky="ew", padx=20, pady=20)
        self.target_frame.columnconfigure(0, weight=1)
        self.target_frame.columnconfigure(1, weight=0)
        self.new_target_entry = customtkinter.CTkEntry(
            self.target_frame,
            placeholder_text=self.old_target,
            corner_radius=10,
            width=250,
        )
        self.new_target_entry.grid(row=0, column=0, sticky="ew", padx=(10, 5), pady=10)
        self.new_target_entry.bind("<KeyRelease>", self.check_target_for_vars)
        self.manage_vars_button = customtkinter.CTkButton(
            self.target_frame,
            text="Manage variables",
            width=80,
            command=self.open_manage_vars_window,
        )
        self.manage_vars_button.grid(row=0, column=1, sticky="ew", padx=(5, 10), pady=10)

        customtkinter.CTkButton(
            self,
            corner_radius=10,
            width=250,
            text="Update Command",
            command=self.update_command,
        ).grid(row=9, column=0, sticky="ew", padx=20, pady=3)

        customtkinter.CTkButton(
            self,
            corner_radius=10,
            width=250,
            text="Restore previous entries",
            command=self.restore_command,
        ).grid(row=10, column=0, sticky="ew", padx=20, pady=3)

        customtkinter.CTkButton(
            self,
            corner_radius=10,
            width=250,
            text="Cancel",
            command=self.destroy,
        ).grid(row=11, column=0, sticky="ew", padx=20, pady=3)

        self.status_label = customtkinter.CTkLabel(self, text="", text_color="#FA0000")
        self.status_label.grid(row=12, column=0, sticky="ew", padx=20, pady=(0, 5))
        self.check_target_for_vars()

    def check_target_for_vars(self, event=None):
        target_text = self.new_target_entry.get()
        variables = set(re.findall(r"\{([^}]+)\}", target_text))

        if variables:
            self.manage_vars_button.grid(row=0, column=1, sticky="w", padx=(0, 20))
        else:
            self.manage_vars_button.grid_forget()
            self.temp_target_vars = {}

    def open_manage_vars_window(self):
        target_text = self.new_target_entry.get()
        variables = sorted(list(set(re.findall(r'\{([^}]+)\}', target_text))))

        if not variables:
            return

        ManageVarsWindow(
            self,
            var_list=variables,
            existing_vars=self.temp_target_vars,
            callback=self.update_temp_vars
        )

    def update_temp_vars(self, new_vars_dict):
        self.temp_target_vars = new_vars_dict
        print(f"EditCommandWindow updated temp_target_vars: {self.temp_target_vars}")

    def restore_command(self):
        self.new_name_entry.delete(0, "end")
        self.new_desc_entry.delete(0, "end")
        self.new_target_entry.delete(0, "end")
        self.new_name_entry.insert(0, self.old_name)
        self.new_desc_entry.insert(0, self.old_description)
        self.new_action_type_option_menu.set(self.old_action_type)
        self.new_target_entry.insert(0, self.old_target)
        self.check_target_for_vars()

    def update_command(self):
        new_name = self.new_name_entry.get().strip()
        new_description = self.new_desc_entry.get().strip()
        new_action_type = self.new_action_type_option_menu.get().strip()
        new_target = self.new_target_entry.get().strip()


        if not new_description:
            new_description = "User's custom command"
        original_target_vars = self.original_command[5] if len(self.original_command) == 6 else {}
        new_command = (new_name, new_description, new_action_type, new_target, "CUSTOM", self.temp_target_vars)
        if not (new_name and new_target):
            self.status_label.configure(text="Name and Target cannot be left blank", text_color="#FA0000")
            return

        if new_name not in [cmd[0] for cmd in self.master_app.commands if cmd != self.original_command]:
            self.master_app.commands = [tuple(cmd) for cmd in self.master_app.commands if cmd != self.original_command]
            self.master_app.new_commands = [tuple(cmd) for cmd in self.master_app.new_commands if cmd != self.original_command]
            self.master_app.command_history = [tuple(cmd) for cmd in self.master_app.command_history if cmd != self.original_command]
            self.master_app.commands.append(new_command)
            self.master_app.new_commands.append(new_command)
            self.master_app.save_command()
            self.status_label.configure(text=f"command ({new_name}) successfully updated", text_color="#00FA00")
            self.master_app.filter_query(None)
            self.master_app.render_results(self.master_app.filtered_commands, self.master_app.command_history)
            self.master_app.last_command.configure(text=f"Updated command: from - {self.old_name} to - {new_name}")
        else:
            self.status_label.configure(text=f"command ({new_name}) already exists", text_color="#FA0000")

if __name__ == "__main__":
    app = CTkinterApplication()
    app.mainloop()
