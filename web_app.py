# web_app.py (v2.29 - Deployment Ready)
import streamlit as st
import json
import os
import extra_streamlit_components as stx
import time

from asana_api_client import AsanaClient
from app_context import AppContext
from ui_components import cor_dog_reason_selector
from camera_component import barcode_scanner_component
from web_operations import (
    process_heater_board_swap,
    process_device_cleaned,
    process_device_complete,
    process_dog_operation,
    process_cor_operation,
    process_custom_operation,
    process_move_cart,
    _find_and_validate_tasks
)

# --- Configuration ---
try:
    ASANA_TOKEN = st.secrets["ASANA_TOKEN"]
except (FileNotFoundError, KeyError):
    st.error("Secrets file not found or ASANA_TOKEN is missing. Please create a .streamlit/secrets.toml file.")
    st.stop()
CONFIG_FILE = "config.json"

st.set_page_config(layout="wide")

# --- App State Management ---
if 'wip_input' not in st.session_state: st.session_state.wip_input = ""
if 'custom_wip_input' not in st.session_state: st.session_state.custom_wip_input = ""
if 'cart_tag_input' not in st.session_state: st.session_state.cart_tag_input = ""
if 'barcode_formula_input' not in st.session_state: st.session_state.barcode_formula_input = ""
if 'log' not in st.session_state: st.session_state.log = []
if 'last_op_result' not in st.session_state: st.session_state.last_op_result = None
if 'custom_recipe' not in st.session_state: st.session_state.custom_recipe = []
if 'device_name' not in st.session_state: st.session_state.device_name = None

# --- Helper Functions ---
@st.cache_resource
def initialize_app():
    if not os.path.exists(CONFIG_FILE): return None, f"Error: {CONFIG_FILE} not found."
    with open(CONFIG_FILE, 'r') as f: config = json.load(f)
    client = AsanaClient(token=ASANA_TOKEN, workspace_id=config.get("workspace_id"))
    context = AppContext(client, config)
    errors = context.resolve_gids()
    if errors: return None, f"Critical Error: Could not find required GIDs: {', '.join(errors)}"
    return context, None

def log_result(result):
    st.session_state.log.insert(0, result['message'])
    st.session_state.last_op_result = result

def run_operation(operation_func, context, *args):
    device_name = st.session_state.device_name
    if not device_name:
        st.warning("Device name not set. Please refresh and set a device name.")
        return
    if not args[0] and operation_func != process_device_complete:
        st.warning("Please provide a valid input (WIP or Cart Tag).")
        return
    full_args = args + (device_name,)
    with st.spinner("Processing..."):
        result = operation_func(context, *full_args)
        log_result(result)
        if result.get("fallback_needed"): st.session_state.manual_wip_needed = True
        else: st.session_state.manual_wip_needed = False
    st.rerun()

def build_recipe_ui(context):
    st.subheader("Barcode Formula")
    st.info("Construct or scan a barcode: `TARGET:COMMAND:Value;` (e.g., `SUB:TAG:New Tag`)")
    
    col1, col2 = st.columns([5, 1])
    with col1:
        # Using a placeholder and hiding the label for better alignment
        barcode_input_val = st.text_input(
            "Scan a formula barcode here (optional):", 
            key="barcode_formula_input", 
            label_visibility="collapsed",
            placeholder="Scan a formula barcode here (optional):"
        )
    with col2:
        with st.popover("📷", use_container_width=True):
            scanned_value = barcode_scanner_component(key="formula_scanner")
            if scanned_value:
                st.session_state.barcode_formula_input = scanned_value
                st.rerun()

    st.markdown("---")
    st.subheader("Manual Recipe Builder")
    col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
    with col1:
        action_type_input = st.selectbox("Action:", ["Add Tag", "Remove Tag", "Assign To", "Add Comment", "Move to Section"], key="action_type")
    with col2:
        is_move_action = action_type_input == "Move to Section"
        target_input = st.radio("Target:", ["Subtask", "Main Task"], key="target_type", index=1 if is_move_action else 0, disabled=is_move_action)
    with col3:
        if action_type_input == "Assign To":
            user_names = [u['name'] for u in context.config.get('users', [])]
            action_value_input = st.selectbox("Value (User Name):", user_names, key="action_value")
        elif action_type_input in ["Add Tag", "Remove Tag"]:
            tag_names = sorted([t['name'] for t in context.config.get('tags', [])])
            action_value_input = st.selectbox("Value (Tag Name):", tag_names, key="action_value")
        elif action_type_input == "Move to Section":
            section_names = sorted([s['name'] for p in context.config.get('projects', []) for s in p.get('sections', [])])
            action_value_input = st.selectbox("Value (Section Name):", section_names, key="action_value")
        else:
            action_value_input = st.text_input("Value:", key="action_value")
    with col4:
        st.write("") 
        if st.button("Add to Recipe"):
            action_map = {"Add Tag": "add_tag", "Remove Tag": "remove_tag", "Assign To": "assign_to", "Move to Section": "move_to", "Add Comment": "add_comment"}
            final_target = "main" if action_type_input == "Move to Section" else target_input.lower()
            st.session_state.custom_recipe.append({'type': action_map[action_type_input], 'value': action_value_input, 'target': final_target})
            st.rerun()
    st.markdown("---")
    st.subheader("Current Recipe")
    if st.session_state.custom_recipe:
        for i, action in enumerate(st.session_state.custom_recipe):
            st.text(f"{i+1}. ({action.get('target', 'subtask').capitalize()}) {action['type']}: {action['value']}")
    else: st.info("Your recipe is empty.")
    if st.button("Clear Recipe"):
        st.session_state.custom_recipe = []
        st.rerun()
    return barcode_input_val

# --- Main App ---
st.title("Asana Automation Portal")
cookie_manager = stx.CookieManager()
st.session_state.device_name = cookie_manager.get(cookie='device_name')

if not st.session_state.device_name:
    st.header("One-Time Device Setup")
    st.info("Please provide a name for this device (e.g., 'Jax Laptop', 'Front Desk PC'). This will be used to tag your actions in Asana.")
    with st.form(key="device_name_form"):
        new_name = st.text_input("Enter Device Name:")
        submitted = st.form_submit_button("Save and Continue")
        if submitted and new_name:
            cookie_manager.set('device_name', new_name, expires_at=None)
            st.success("Device name saved! Loading application...")
            time.sleep(1)
            st.rerun()
else:
    context, error = initialize_app()
    if error: st.error(error)
    else:
        st.sidebar.markdown(f"**Device:** `{st.session_state.device_name}`")
        if st.sidebar.button("Change Device Name"):
            cookie_manager.delete('device_name', key="delete_cookie")
            st.rerun()
        if st.session_state.last_op_result:
            if st.session_state.last_op_result.get('success'): st.success(st.session_state.last_op_result['message'])
            elif not st.session_state.get('manual_wip_needed'): st.error(st.session_state.last_op_result['message'])
            st.session_state.last_op_result = None
        st.sidebar.title("Operations")
        mode = st.sidebar.radio("Choose an operation:", ("Heater Board Swapped", "Device Cleaned", "Device Complete", "Dog Operation", "COR Operation", "Custom Operation", "Move Cart"))
        st.header(mode)
        
        if mode in ("Custom Operation", "Move Cart"):
            barcode_input = build_recipe_ui(context)
            st.markdown("---")
            form_key = f"{mode.replace(' ', '_').lower()}_form"
            with st.form(key=form_key, clear_on_submit=True):
                if mode == "Custom Operation":
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        wip_input = st.text_input("Enter WIP Number:", key="custom_wip_input", placeholder="Enter WIP Number to run recipe:", label_visibility="collapsed")
                    with col2:
                        with st.popover("📷", use_container_width=True):
                            scanned_value = barcode_scanner_component(key="custom_op_scanner")
                            if scanned_value:
                                st.session_state.custom_wip_input = scanned_value
                                st.rerun()
                else: # Move Cart
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        cart_tag_name = st.text_input("Enter Cart Tag Name:", key="cart_tag_input", placeholder="Enter the Cart Tag Name:", label_visibility="collapsed")
                    with col2:
                        with st.popover("📷", use_container_width=True):
                            scanned_value = barcode_scanner_component(key="cart_tag_scanner")
                            if scanned_value:
                                st.session_state.cart_tag_input = scanned_value
                                st.rerun()
                submitted = st.form_submit_button(f"Run {mode}")
                if submitted:
                    recipe = []
                    if barcode_input:
                        try:
                            actions = barcode_input.split(';'); action_map = {"TAG": "add_tag", "REMOVE_TAG": "remove_tag", "ASSIGN": "assign_to", "MOVE": "move_to", "COMMENT": "add_comment"}; target_map = {"SUB": "subtask", "MAIN": "main"}
                            for action in actions:
                                parts = action.split(':', 2)
                                if len(parts) == 3: target, command, value = parts; recipe.append({'type': action_map[command.upper().strip()], 'target': target_map[target.upper().strip()], 'value': value.strip()})
                                elif len(parts) == 2: command, value = parts; recipe.append({'type': action_map[command.upper().strip()], 'target': 'subtask', 'value': value.strip()})
                        except Exception as e: st.error(f"Invalid barcode formula syntax: {e}"); recipe = []
                    else: recipe = st.session_state.custom_recipe
                    if not recipe: st.warning("Cannot run an empty recipe.")
                    elif mode == "Custom Operation": run_operation(process_custom_operation, context, wip_input, recipe)
                    elif mode == "Move Cart":
                        if cart_tag_name: run_operation(process_move_cart, context, cart_tag_name, recipe)
                        else: st.warning("Please provide a Cart Tag Name.")
        elif mode == "Device Complete":
            with st.form(key="device_complete_form", clear_on_submit=True):
                uploaded_file = st.file_uploader("Upload Certificate", type=['xlsx'])
                if st.session_state.get('manual_wip_needed'):
                    st.warning(st.session_state.log[0])
                    manual_wip = st.text_input("Please enter WIP number manually:")
                else: manual_wip = None
                submitted = st.form_submit_button("Run Operation")
                if submitted:
                    if uploaded_file:
                        file_data = {"file_name": uploaded_file.name, "file_content": uploaded_file.getvalue(), "content_type": uploaded_file.type}
                        run_operation(process_device_complete, context, file_data, manual_wip)
                    else: st.warning("Please upload a certificate file.")
        else: # Standard Operations
            col1, col2 = st.columns([5, 1])
            with col1:
                wip_input = st.text_input("Enter WIP Number:", key="wip_input", placeholder="Enter WIP Number:", label_visibility="collapsed")
            with col2:
                with st.popover("📷", use_container_width=True):
                    scanned_value = barcode_scanner_component(key="std_op_scanner")
                    if scanned_value:
                        st.session_state.wip_input = scanned_value
                        if 'validated_wip' in st.session_state: st.session_state.validated_wip = None
                        st.rerun()
            
            if mode in ("Dog Operation", "COR Operation"):
                if wip_input and st.session_state.get('validated_wip') != wip_input:
                    with st.spinner("Validating WIP..."):
                        task_validation = _find_and_validate_tasks(context, wip_input)
                        st.session_state.task_validation_result = task_validation
                        st.session_state.validated_wip = wip_input if task_validation.get("success") else "fail"
                    st.rerun()

                reason_data, is_order_hold, order_hold_reason = None, False, ""
                if wip_input and st.session_state.get('validated_wip') == wip_input:
                    task_validation = st.session_state.task_validation_result
                    if task_validation["success"]:
                        if mode == "Dog Operation":
                            parent_gid = task_validation["parent_gid"]
                            parent_data_result = context.client.get_task_details(parent_gid, opt_fields="projects.gid")
                            parent_data = parent_data_result.get("data",{}).get("data",{})
                            if not any(p.get('gid') == context.gids.get("PROJECT_AMAT_AGS") for p in parent_data.get('projects', [])):
                                st.subheader("Order Hold Workflow")
                                is_order_hold = st.checkbox("Is this an ORDER HOLD?")
                                order_hold_reason = st.text_input("Why is it an ORDER HOLD?")
                        st.markdown("---")
                        st.subheader("Standard Reason")
                        reason_data = cor_dog_reason_selector()
                elif wip_input and st.session_state.get('validated_wip') == "fail":
                     st.error(st.session_state.get('task_validation_result', {}).get('message', 'Validation failed.'))
                elif not wip_input:
                    st.info("Enter or scan a WIP number to see actions.")

                with st.form(key=f"{mode}_form_submit", clear_on_submit=True):
                    submitted = st.form_submit_button("Run Operation")
                    if submitted:
                        st.session_state.validated_wip = None 
                        st.session_state.wip_input = "" # Clear input on submit
                        if mode == "Dog Operation":
                            run_operation(process_dog_operation, context, wip_input, reason_data, order_hold_reason)
                        elif mode == "COR Operation":
                            run_operation(process_cor_operation, context, wip_input, reason_data)
            else: # Heater Board & Cleaned
                with st.form(key=f"{mode}_form", clear_on_submit=True):
                    submitted = st.form_submit_button("Run Operation")
                    if submitted:
                        st.session_state.wip_input = ""
                        if mode == "Heater Board Swapped": run_operation(process_heater_board_swap, context, wip_input)
                        elif mode == "Device Cleaned": run_operation(process_device_cleaned, context, wip_input)

        st.markdown("---")
        st.subheader("Activity Log")
        if st.button("Clear Log"):
            st.session_state.log = []
            st.session_state.last_op_result = None
            st.rerun()
        for entry in st.session_state.log:
            st.info(entry)