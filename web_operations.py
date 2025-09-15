# web_operations.py (v2.24)
import logging
import os

def _find_and_validate_tasks(context, wip_number):
    # This function is correct and unchanged
    opt_fields = "name,gid,parent,projects.gid,tags.gid"
    wip_lower = wip_number.lower()
    initial_task_result = context.client.find_task_by_wip(wip_number, opt_fields=opt_fields)
    if not initial_task_result["success"]: return initial_task_result
    task_data = initial_task_result["task_data"]
    parent_gid = None; subtask_gid = None
    parent_info = task_data.get('parent')
    if parent_info:
        parent_gid = parent_info.get('gid')
        if wip_lower in task_data.get('name', '').lower():
            subtask_gid = task_data.get('gid')
        else:
            subtasks_result = context.client.get_subtasks_for_task(parent_gid)
            if not subtasks_result["success"]: return subtasks_result
            subtasks = subtasks_result.get("data", {}).get("data", [])
            matching_subtask = next((st for st in subtasks if wip_lower in st.get('name', '').lower()), None)
            if matching_subtask: subtask_gid = matching_subtask['gid']
            else: return {"success": False, "message": f"Found a related task, but no subtask with '{wip_number}' in its name."}
    else:
        parent_gid = task_data.get('gid')
        subtasks_result = context.client.get_subtasks_for_task(parent_gid)
        if not subtasks_result["success"]: return subtasks_result
        subtasks = subtasks_result.get("data", {}).get("data", [])
        matching_subtask = next((st for st in subtasks if wip_lower in st.get('name', '').lower()), None)
        if not matching_subtask: return {"success": False, "message": f"No subtask for '{wip_number}' found under the main task."}
        subtask_gid = matching_subtask['gid']
    parent_details = context.client.get_task_details(parent_gid, opt_fields="name,tags.gid,projects.gid")
    parent_data = parent_details.get("data", {}).get("data", {}); parent_tags = {tag['gid'] for tag in parent_data.get("tags", [])}
    if context.gids.get("PURGE_TAG") in parent_tags:
        return {"success": False, "message": f"ERROR: Parent task '{parent_data.get('name')}' has the PURGE tag."}
    return {"success": True, "parent_gid": parent_gid, "subtask_gid": subtask_gid}

def _resolve_name_or_gid(value, raw_config):
    # This helper is correct and unchanged
    if value.isdigit(): return value, None
    search_lists = { 'User': raw_config.get('users', []), 'Tag': raw_config.get('tags', []) }
    for item_type, item_list in search_lists.items():
        for item in item_list:
            if item.get('name', '').strip().lower() == value.strip().lower(): return item['gid'], None
    for project in raw_config.get('projects', []):
        if project.get('name', '').strip().lower() == value.strip().lower(): return project['gid'], None
        for section in project.get('sections', []):
            if section.get('name', '').strip().lower() == value.strip().lower(): return section['gid'], None
    return None, f"Could not find GID for name '{value}'."

def process_heater_board_swap(context, wip_number, device_name):
    # This function is correct and unchanged
    task_validation = _find_and_validate_tasks(context, wip_number)
    if not task_validation["success"]: return task_validation
    subtask_gid = task_validation["subtask_gid"]
    tag_gid = context.gids.get("HEATER_SWAP_TAGS", [None])[0]
    if not tag_gid: return {"success": False, "message": "Heater Board Replacement tag not found in config."}
    add_tag_result = context.client.add_tag_to_task(subtask_gid, tag_gid)
    if not add_tag_result["success"]: return add_tag_result
    comment = f"Heater Board Swapped ~{device_name}"
    context.client.add_comment_to_task(subtask_gid, comment)
    return {"success": True, "message": f"WIP {wip_number}: Added Heater Board Swapped tag."}

def process_device_cleaned(context, wip_number, device_name):
    # This function is correct and unchanged
    task_validation = _find_and_validate_tasks(context, wip_number)
    if not task_validation["success"]: return task_validation
    subtask_gid = task_validation["subtask_gid"]
    tag_gid = context.gids.get("CLEANED_TAG")
    if not tag_gid: return {"success": False, "message": "Tag 'Cleaned' not found in config."}
    add_tag_result = context.client.add_tag_to_task(subtask_gid, tag_gid)
    if not add_tag_result["success"]: return add_tag_result
    comment = f"Device Cleaned ~{device_name}"
    context.client.add_comment_to_task(subtask_gid, comment)
    return {"success": True, "message": f"WIP {wip_number}: Added Cleaned tag."}

def process_device_complete(context, uploaded_file_data, manual_wip, device_name):
    # This function is correct and unchanged
    if manual_wip: wip_to_search = manual_wip
    else: wip_to_search = os.path.splitext(uploaded_file_data['file_name'])[0]
    task_validation = _find_and_validate_tasks(context, wip_to_search)
    if not task_validation["success"]:
        return {"success": False, "message": f"Could not find task for '{wip_to_search}'. Please provide WIP manually.", "fallback_needed": True}
    subtask_gid = task_validation["subtask_gid"]
    parent_gid = task_validation["parent_gid"]
    parent_data_result = context.client.get_task_details(parent_gid, opt_fields="projects.gid")
    parent_data = parent_data_result.get("data", {}).get("data", {})
    is_amat_ags = any(p.get('gid') == context.gids.get("PROJECT_AMAT_AGS") for p in parent_data.get('projects', []))
    all_ops_success, messages = True, []
    def log_op(msg, res):
        nonlocal all_ops_success
        if not res["success"]: all_ops_success = False
        messages.append(f"• {msg}: {'Success' if res['success'] else 'FAILED'}")
    log_op("Uploading certificate", context.client.upload_attachment(subtask_gid, uploaded_file_data))
    log_op(f"Assigning subtask", context.client.assign_task_to_user(subtask_gid, context.gids.get("SHARED_SUBTASK_ASSIGNEE")))
    log_op(f"Adding tag 'Device Calibrated'", context.client.add_tag_to_task(subtask_gid, context.gids.get("DEVICE_COMPLETE_TAG")))
    comment = f"AUTO: Device Complete ~{device_name}"
    log_op("Adding comment", context.client.add_comment_to_task(subtask_gid, comment))
    if is_amat_ags:
        log_op(f"Assigning parent task", context.client.assign_task_to_user(parent_gid, context.gids.get("ACCOUNT_MANAGER_ASSIGNEE")))
        ready_for_buyer_gid = context.gids.get("READY_FOR_BUYER_SECTION")
        if ready_for_buyer_gid:
            log_op("Moving parent task", context.client.move_task_to_section(parent_gid, ready_for_buyer_gid))
    summary = f"Device Complete for '{wip_to_search}' finished."
    final_message = f"{summary}\n\n--- Details ---\n" + "\n".join(messages)
    return {"success": all_ops_success, "message": final_message}

def process_dog_operation(context, wip_number, reason_data, order_hold_reason, device_name):
    # This function is correct and unchanged
    task_validation = _find_and_validate_tasks(context, wip_number)
    if not task_validation["success"]: return task_validation
    subtask_gid = task_validation["subtask_gid"]
    all_ops_success, messages = True, []
    def log_op(msg, res):
        nonlocal all_ops_success
        if not res["success"]: all_ops_success = False
        messages.append(f"• {msg}: {'Success' if res['success'] else 'FAILED'}")
    if order_hold_reason:
        comment = f"AUTO: ORDER HOLD - {order_hold_reason} ~{device_name}"
        log_op("Assigning to Susan Hearon", context.client.assign_task_to_user(subtask_gid, context.gids.get("SUSAN_HEARON_USER")))
        log_op("Adding tag 'Order Hold'", context.client.add_tag_to_task(subtask_gid, context.gids.get("ORDER_HOLD_TAG")))
        log_op("Adding ORDER HOLD comment", context.client.add_comment_to_task(subtask_gid, comment))
    log_op("Adding tag 'DOG'", context.client.add_tag_to_task(subtask_gid, context.gids.get("DOG_TAG")))
    if reason_data:
        comment = f"{reason_data['comment']} ~{device_name}"
        log_op("Adding reason comment", context.client.add_comment_to_task(subtask_gid, comment))
        if reason_data['tag_name_to_add']:
            tag_key = f"{reason_data['tag_name_to_add'].upper().replace(' ', '_')}_TAG"
            tag_gid = context.gids.get(tag_key)
            log_op(f"Adding tag '{reason_data['tag_name_to_add']}'", context.client.add_tag_to_task(subtask_gid, tag_gid))
    summary = f"Dog Operation for WIP {wip_number} finished."
    final_message = f"{summary}\n\n--- Details ---\n" + "\n".join(messages)
    return {"success": all_ops_success, "message": final_message}

def process_cor_operation(context, wip_number, reason_data, device_name):
    # This function is correct and unchanged
    task_validation = _find_and_validate_tasks(context, wip_number)
    if not task_validation["success"]: return task_validation
    subtask_gid = task_validation["subtask_gid"]
    parent_gid = task_validation["parent_gid"]
    parent_data_result = context.client.get_task_details(parent_gid, opt_fields="name,projects.gid")
    subtask_data_result = context.client.get_task_details(subtask_gid, opt_fields="name")
    parent_data = parent_data_result.get("data", {}).get("data", {})
    subtask_data = subtask_data_result.get("data", {}).get("data", {})
    is_amat_ags = any(p.get('gid') == context.gids.get("PROJECT_AMAT_AGS") for p in parent_data.get('projects', []))
    all_ops_success, messages = True, []
    def log_op(msg, res):
        nonlocal all_ops_success
        if not res["success"]: all_ops_success = False
        messages.append(f"• {msg}: {'Success' if res['success'] else 'FAILED'}")
    comment = f"{reason_data['comment']} ~{device_name}"
    log_op("Adding reason comment", context.client.add_comment_to_task(subtask_gid, comment))
    if reason_data['tag_name_to_add']:
        tag_key = f"{reason_data['tag_name_to_add'].upper().replace(' ', '_')}_TAG"
        tag_gid = context.gids.get(tag_key)
        log_op(f"Adding tag '{reason_data['tag_name_to_add']}'", context.client.add_tag_to_task(subtask_gid, tag_gid))
    log_op("Adding tag 'Return Unrepaired'", context.client.add_tag_to_task(subtask_gid, context.gids.get("COR_TAG")))
    if not subtask_data.get('name', '').strip().upper().startswith("*COR*"):
        log_op("Renaming subtask", context.client.change_task_name(subtask_gid, f"*COR* {subtask_data.get('name')}"))
    if is_amat_ags:
        if not parent_data.get('name', '').strip().upper().startswith("*COR*"):
            log_op("Renaming parent", context.client.change_task_name(parent_gid, f"*COR* {parent_data.get('name')}"))
        log_op("Assigning parent", context.client.assign_task_to_user(parent_gid, context.gids.get("ACCOUNT_MANAGER_ASSIGNEE")))
        log_op("Assigning subtask", context.client.assign_task_to_user(subtask_gid, context.gids.get("SHARED_SUBTASK_ASSIGNEE")))
        log_op("Moving parent", context.client.move_task_to_section(parent_gid, context.gids.get("NEEDS_COR_SECTION")))
    summary = f"COR Operation for WIP {wip_number} finished."
    final_message = f"{summary}\n\n--- Details ---\n" + "\n".join(messages)
    return {"success": all_ops_success, "message": final_message}

def process_custom_operation(context, wip_number, recipe, device_name):
    task_validation = _find_and_validate_tasks(context, wip_number)
    if not task_validation["success"]: return task_validation
    subtask_gid = task_validation["subtask_gid"]
    parent_gid = task_validation["parent_gid"]
    all_ops_success, messages = True, []
    def log_op(msg, res):
        nonlocal all_ops_success
        if not res["success"]: all_ops_success = False
        status = 'Success' if res["success"] else f"FAILED: {res.get('message', 'Unknown')}"
        messages.append(f"• {msg}: {status}")
    for action in recipe:
        action_type = action['type']; value = action['value']; target = action.get('target', 'subtask')
        target_gid = subtask_gid if target == 'subtask' else parent_gid
        if action_type == 'move_to': target_gid = parent_gid
        gid_to_use, error_msg = value, None
        if action_type != 'add_comment':
            gid_to_use, error_msg = _resolve_name_or_gid(value, context.config)
        if error_msg:
            log_op(f"Action '{action_type}' for '{value}'", {"success": False, "message": error_msg})
            continue
        if action_type == 'add_tag': log_op(f"Adding tag '{value}' to {target}", context.client.add_tag_to_task(target_gid, gid_to_use))
        elif action_type == 'remove_tag': log_op(f"Removing tag '{value}' from {target}", context.client.remove_tag_from_task(target_gid, gid_to_use))
        elif action_type == 'assign_to': log_op(f"Assigning {target} to '{value}'", context.client.assign_task_to_user(target_gid, gid_to_use))
        elif action_type == 'move_to': log_op(f"Moving main task to section '{value}'", context.client.move_task_to_section(target_gid, gid_to_use))
        elif action_type == 'add_comment': log_op(f"Adding comment to {target}", context.client.add_comment_to_task(target_gid, f"AUTO: {value}"))
    
    # --- CHANGE: Formatted recipe summary for better readability ---
    recipe_lines = [f"  • Target: {a.get('target', 'subtask').capitalize()} | Action: {a['type']} | Value: '{a['value']}'" for a in recipe]
    recipe_summary = "\n".join(recipe_lines)
    final_comment = f"AUTO: Custom Recipe Executed:\n{recipe_summary}\n\n~{device_name}"

    context.client.add_comment_to_task(subtask_gid, final_comment)
    summary = f"Custom operation for WIP {wip_number} finished."
    final_message = f"{summary}\n\n--- Details ---\n" + "\n".join(messages)
    return {"success": all_ops_success, "message": final_message}

def process_move_cart(context, cart_tag_name, recipe, device_name):
    # This function is correct and unchanged
    cart_tag_gid, error_msg = _resolve_name_or_gid(cart_tag_name, context.config)
    if error_msg: return {"success": False, "message": error_msg}
    tasks_result = context.client.get_tasks_by_tag(cart_tag_gid)
    if not tasks_result["success"]: return tasks_result
    tasks = tasks_result.get("data", {}).get("data", [])
    if not tasks: return {"success": False, "message": f"No tasks found with tag '{cart_tag_name}'."}
    success_count = 0; failed_tasks = []
    for task in tasks:
        wip_name = task.get('name', '')
        result = process_custom_operation(context, wip_name, recipe, device_name)
        if result["success"]: success_count += 1
        else: failed_tasks.append(f"• {wip_name}: {result['message']}")
    summary = f"Move Cart '{cart_tag_name}' complete. Success: {success_count}, Failed: {len(failed_tasks)}."
    if failed_tasks:
        final_message = f"{summary}\n\n--- Failures ---\n" + "\n".join(failed_tasks)
    else:
        final_message = summary
    return {"success": success_count > 0, "message": final_message}