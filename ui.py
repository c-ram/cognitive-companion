import gradio as gr
import requests

API_URL = "http://api.nanai.khoofia.com:8100"

def analyze_media(prompt, file):
    if not file:
        return "No file uploaded."
    try:
        with open(file, "rb") as f:
            response = requests.post(f"{API_URL}/analyze", data={"prompt": prompt}, files={"file": f})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return f"Error: {str(e)}"

def translate_wrapper(prompt):
    try:
        response = requests.post(f"{API_URL}/translate", json={"prompt": prompt})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# --- API Fetch Wrappers ---
def get_rules_df():
    try:
        resp = requests.get(f"{API_URL}/rules")
        return [
            [r["id"], r["name"], r.get("description", ""), r["enabled"], r.get("schedule_cron", ""), r.get("cool_off_minutes", 0), r.get("max_daily_triggers", 0)]
            for r in resp.json()
        ]
    except Exception:
        return []

def get_contexts_wrapper(r_id):
    if not r_id: return []
    try:
        resp = requests.get(f"{API_URL}/rules/{int(r_id)}/contexts")
        resp.raise_for_status()
        return [
            [c["id"], c["context_type"], c.get("start_time", ""), c.get("end_time", ""), c.get("room_name", "")]
            for c in resp.json()
        ]
    except Exception:
        return []

def get_sensors_df():
    try:
        resp = requests.get(f"{API_URL}/sensors")
        return [[s["id"], s["name"], s["room_name"], s["type"], s["enabled"]] for s in resp.json()]
    except Exception:
        return []

# --- UI Components ---
def create_vision_tab():
    with gr.Tab("Vision"):
        gr.Markdown("### Debug Vision Language Model")
        with gr.Row():
            with gr.Column(scale=1):
                prompt_input = gr.Textbox(label="Prompt", value="Describe this content.")
                file_input = gr.File(label="Upload Image or Video")
                analyze_btn = gr.Button("Analyze", variant="primary")
            with gr.Column(scale=2):
                output_json = gr.JSON(label="API Response")
        
        analyze_btn.click(fn=analyze_media, inputs=[prompt_input, file_input], outputs=output_json)

def create_translation_tab():
    with gr.Tab("Translation"):
        gr.Markdown("### Debug Translation Model")
        with gr.Row():
            with gr.Column(scale=1):
                trans_prompt = gr.Textbox(label="Text to Translate", placeholder="Enter Tamil text here...", lines=4)
                trans_btn = gr.Button("Translate", variant="primary")
            with gr.Column(scale=2):
                trans_output = gr.JSON(label="Translation Result")
                
        trans_btn.click(fn=translate_wrapper, inputs=trans_prompt, outputs=trans_output)

def create_rules_tab():
    with gr.Tab("Rule Management"):
        gr.Markdown("### Manage Automated Workflow Rules")
        
        with gr.Row():
            refresh_rules_btn = gr.Button("Refresh Rules", variant="secondary")
        
        rule_list = gr.DataFrame(
            headers=["ID", "Name", "Desc", "Enabled", "Cron", "Min Cooldown", "Max Triggers"], 
            datatype=["number", "str", "str", "bool", "str", "number", "number"], 
            label="Existing Rules", 
            interactive=False
        )
        
        with gr.Row():
            # Rule Editor Column
            with gr.Column(scale=1, variant="panel"):
                gr.Markdown("#### Create / Edit Rule")
                rule_id_input = gr.Number(label="Target Rule ID (Leave empty for Create)", precision=0)
                rule_name = gr.Textbox(label="Name", placeholder="e.g. Morning Check")
                rule_desc = gr.Textbox(label="Description", lines=2)
                rule_enabled = gr.Checkbox(label="Enabled", value=True)
                rule_cron = gr.Textbox(label="Cron Schedule", placeholder="e.g. 0 8 * * *")
                
                with gr.Accordion("Advanced Rule Settings", open=False):
                    rule_vision = gr.Textbox(label="Vision Prompt", value="Describe this image in detail.", lines=2)
                    rule_logic = gr.Textbox(label="Logic Prompt", value="Based on the description, decide if an action is needed.", lines=2)
                    rule_feedback = gr.Textbox(label="Feedback Template", value="Notification: {result}")
                    rule_cool = gr.Number(label="Cool Off Minutes", value=5, precision=0)
                    rule_max = gr.Number(label="Max Daily Triggers", value=3, precision=0)

                with gr.Row():
                    create_rule_btn = gr.Button("Save Rule", variant="primary")
                    delete_rule_btn = gr.Button("Delete Rule", variant="stop")
                rule_status_msg = gr.Textbox(label="Rule Status", interactive=False)

            # Context Editor Column
            with gr.Column(scale=1, variant="panel"):
                gr.Markdown("#### Context Management")
                target_rule_id = gr.Number(label="Target Rule ID for Contexts", precision=0)
                
                context_list = gr.DataFrame(headers=["ID", "Type", "Start", "End", "Room"], interactive=False)
                refresh_ctx_btn = gr.Button("View Contexts for Rule", variant="secondary")
                
                gr.Markdown("**Add Context**")
                ctx_type = gr.Dropdown(choices=["time_range", "room"], label="Context Type")
                with gr.Row():
                    ctx_start = gr.Textbox(label="Start (HH:MM)")
                    ctx_end = gr.Textbox(label="End (HH:MM)")
                    ctx_room = gr.Textbox(label="Room Name")
                add_ctx_btn = gr.Button("Add Context", variant="primary")
                
                gr.Markdown("**Delete Context**")
                with gr.Row():
                    ctx_id_to_delete = gr.Number(label="Context ID to Delete", precision=0)
                    del_ctx_btn = gr.Button("Delete Context", variant="stop")
                
                ctx_status = gr.Textbox(label="Context Status", interactive=False)

        # Event Handlers
        refresh_rules_btn.click(fn=get_rules_df, inputs=[], outputs=rule_list)
        
        def save_rule(r_id, name, desc, enabled, cron, v, l, f, cool, mx):
            try:
                payload = {"name": name, "description": desc, "enabled": enabled, "schedule_cron": cron, "vision_prompt": v, "logic_prompt": l, "feedback_template": f, "cool_off_minutes": int(cool), "max_daily_triggers": int(mx)}
                if r_id and r_id > 0:
                    resp = requests.put(f"{API_URL}/rules/{int(r_id)}", json=payload)
                    resp.raise_for_status()
                    return "Rule Updated"
                else:
                    resp = requests.post(f"{API_URL}/rules", json=payload)
                    resp.raise_for_status()
                    return "Rule Created"
            except Exception as e:
                err_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    err_msg += f" - Response: {e.response.text}"
                return f"Error: {err_msg}"
                
        create_rule_btn.click(fn=save_rule, inputs=[rule_id_input, rule_name, rule_desc, rule_enabled, rule_cron, rule_vision, rule_logic, rule_feedback, rule_cool, rule_max], outputs=rule_status_msg).then(
            fn=get_rules_df, outputs=rule_list
        )
        
        def delete_rule(r_id):
            if not r_id: return "Enter Rule ID"
            try:
                requests.delete(f"{API_URL}/rules/{int(r_id)}").raise_for_status()
                return "Rule Deleted"
            except Exception as e:
                return f"Error: {e}"
                
        delete_rule_btn.click(fn=delete_rule, inputs=[rule_id_input], outputs=rule_status_msg).then(
            fn=get_rules_df, outputs=rule_list
        )
        
        refresh_ctx_btn.click(fn=get_contexts_wrapper, inputs=[target_rule_id], outputs=context_list)
        
        def add_context(r_id, c_type, start, end, room):
            if not r_id: return "Enter Target Rule ID"
            try:
                payload = {"context_type": c_type}
                if c_type == "time_range":
                    payload.update({"start_time": start, "end_time": end})
                elif c_type == "room":
                    payload["room_name"] = room
                requests.post(f"{API_URL}/rules/{int(r_id)}/context", json=payload).raise_for_status()
                return "Context Added"
            except Exception as e:
                return f"Error: {e}"

        add_ctx_btn.click(fn=add_context, inputs=[target_rule_id, ctx_type, ctx_start, ctx_end, ctx_room], outputs=ctx_status).then(
            fn=get_contexts_wrapper, inputs=[target_rule_id], outputs=context_list
        )
        
        def delete_context(r_id, c_id):
            if not r_id or not c_id: return "Enter Rule and Context ID"
            try:
                requests.delete(f"{API_URL}/rules/{int(r_id)}/context/{int(c_id)}").raise_for_status()
                return "Context Deleted"
            except Exception as e:
                return f"Error: {e}"
        del_ctx_btn.click(fn=delete_context, inputs=[target_rule_id, ctx_id_to_delete], outputs=ctx_status).then(
            fn=get_contexts_wrapper, inputs=[target_rule_id], outputs=context_list
        )
        
        # Populate input forms from dataframe clicks mapping
        def select_rule(evt: gr.SelectData):
            # evt.value returns the cell value, evt.index is [row, col]
            # To be robust, the UI would need the whole row data. This is trickier in basic Gradio.
            # We will at least autofill the target ID based on the selected row.
            return evt.value if isinstance(evt.value, int) else None

        rule_list.select(fn=select_rule, outputs=rule_id_input)
        rule_list.select(fn=select_rule, outputs=target_rule_id)
        
def create_sensors_tab():
    with gr.Tab("Sensor Management"):
        gr.Markdown("### Manage Environment Sensors")
        refresh_sensors_btn = gr.Button("Refresh Sensors", variant="secondary")
        sensor_list = gr.DataFrame(headers=["ID", "Name", "Room", "Type", "Enabled"], interactive=False)
        
        with gr.Group():
            gr.Markdown("#### Input Form")
            with gr.Row():
                s_id = gr.Textbox(label="Sensor ID (e.g. recamera-001)")
                s_name = gr.Textbox(label="Name")
                s_room = gr.Textbox(label="Room Name")
                s_type = gr.Dropdown(choices=["camera", "presence", "button"], label="Type", value="camera")
                s_enabled = gr.Checkbox(label="Enabled", value=True)
                
            with gr.Row():
                create_sensor_btn = gr.Button("Create Sensor", variant="primary")
                update_sensor_btn = gr.Button("Update Sensor", variant="secondary")
                delete_sensor_btn = gr.Button("Delete Sensor", variant="stop")
                
            sensor_status = gr.Textbox(label="Status", interactive=False)

        refresh_sensors_btn.click(fn=get_sensors_df, outputs=sensor_list)
        
        def save_sensor(sid, name, room, stype, enabled, update=False):
            if not sid: return "Sensor ID required"
            try:
                payload = {"name": name, "room_name": room, "type": stype, "enabled": enabled}
                if update:
                    requests.put(f"{API_URL}/sensors/{sid}", json=payload).raise_for_status()
                    return "Sensor Updated"
                else:
                    payload["id"] = sid
                    requests.post(f"{API_URL}/sensors", json=payload).raise_for_status()
                    return "Sensor Created"
            except Exception as e:
                return f"Error: {e}"

        create_sensor_btn.click(fn=lambda sid, n, r, t, e: save_sensor(sid, n, r, t, e, False), inputs=[s_id, s_name, s_room, s_type, s_enabled], outputs=sensor_status).then(
            fn=get_sensors_df, outputs=sensor_list
        )
        update_sensor_btn.click(fn=lambda sid, n, r, t, e: save_sensor(sid, n, r, t, e, True), inputs=[s_id, s_name, s_room, s_type, s_enabled], outputs=sensor_status).then(
            fn=get_sensors_df, outputs=sensor_list
        )

        def delete_sensor(sid):
            if not sid: return "Sensor ID required"
            try:
                requests.delete(f"{API_URL}/sensors/{sid}").raise_for_status()
                return "Sensor Deleted"
            except Exception as e:
                return f"Error: {e}"
        delete_sensor_btn.click(fn=delete_sensor, inputs=[s_id], outputs=sensor_status).then(
            fn=get_sensors_df, outputs=sensor_list
        )

# --- Application Startup ---
_primary = gr.themes.Color(
    c50="#F0EEFF",    # near-white lavender — light mode bg tint
    c100="#D9D4FF",   # soft violet
    c200="#B8AFFF",   # bright light purple — dark mode accent base
    c300="#9489F5",   # vivid medium purple — dark mode button text/borders
    c400="#7060E0",   # bold purple — dark mode primary interactive
    c500="#4D3BB8",   # deep purple — light mode hover
    c600="#36278F",   # dark purple — light mode primary button
    c700="#1B192E",   # brand anchor (#1B192E)
    c800="#130F24",   # deeper navy
    c900="#0B0919",
    c950="#05040D",
)

with gr.Blocks(theme=gr.themes.Soft(primary_hue=_primary)) as console:
    gr.Markdown("# Cognitive Companion Console")
    create_rules_tab()
    create_sensors_tab()
    create_vision_tab()
    create_translation_tab()

    console.load(fn=get_rules_df, outputs=None) # Note: can't easily auto-populate gr.DataFrame on load cleanly without state vars, skipping auto-load for simplicity

if __name__ == "__main__":
    console.launch(server_name="0.0.0.0", server_port=7860)
