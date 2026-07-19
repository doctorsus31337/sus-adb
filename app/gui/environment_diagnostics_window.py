import customtkinter as ctk
class EnvironmentDiagnosticsWindow(ctk.CTkToplevel):
    def __init__(self,parent,theme,records):
        super().__init__(parent);self.title("Environment Diagnostics");self.geometry("820x600");self.transient(parent);self.grid_columnconfigure(0,weight=1);self.grid_rowconfigure(0,weight=1);view=ctk.CTkTextbox(self,fg_color=theme["terminal_bg"],text_color=theme["text"],wrap="word");view.grid(row=0,column=0,sticky="nsew",padx=10,pady=10);view.insert("1.0","\n\n".join(f"{'READY' if r.available else 'MISSING'} · {r.name} · {'Required' if r.required else 'Optional'}\n{r.version or r.path}\n{r.guidance}" for r in records));view.configure(state="disabled")
