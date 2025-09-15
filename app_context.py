# app_context.py (v2.20)
import logging

class AppContext:
    """A centralized object to hold application state and configuration."""
    def __init__(self, asana_client, full_config_data):
        self.client = asana_client
        self.config = full_config_data
        self.gids = {}
        self.resolve_gids()

    def find_gids_by_name(self, item_list, name):
        """Finds all GIDs for a given name, trimming whitespace."""
        return [
            item.get('gid') for item in item_list
            if item.get('name', '').strip().lower() == name.strip().lower()
        ]

    def resolve_gids(self):
        """
        Parses the full config data to find and store the GIDs for all
        required Asana items. Logs warnings for non-critical missing items.
        """
        all_tags = self.config.get('tags', [])
        all_projects = self.config.get('projects', [])
        all_users = self.config.get('users', [])
        
        critical_errors = []
        
        project_gid_list = self.find_gids_by_name(all_projects, "AMAT AGS")
        if not project_gid_list:
            critical_errors.append("Project 'AMAT AGS' not found.")
        else:
            project_gid = project_gid_list[0]
            self.gids["PROJECT_AMAT_AGS"] = project_gid
            project_obj = next((p for p in all_projects if p['gid'] == project_gid), None)
            project_sections = project_obj.get('sections', []) if project_obj else []
            
            section_map = {
                "READY_FOR_BUYER_SECTION": "Ready for Buyer",
                "NEEDS_COR_SECTION": "Needs COR"
            }
            for key, name in section_map.items():
                sec_gids = self.find_gids_by_name(project_sections, name)
                if sec_gids: self.gids[key] = sec_gids[0]
                else: logging.warning(f"Configuration Warning: Section '{name}' not found."); self.gids[key] = None

        tag_map = {
            "HEATER_SWAP_TAGS": "Heater Board Replacement",
            "ORDER_HOLD_TAG": "Order Hold", "DOG_TAG": "DOG",
            "DEVICE_COMPLETE_TAG": "Device Calibrated", "COR_TAG": "Return Unrepaired",
            "PURGE_TAG": "PURGE", "BAD_SENSOR_TAG": "Bad Sensor",
            "PRESSURE_OSCILLATION_TAG": "Pressure Oscillation", "INTERNAL_LEAK_TAG": "INTERNAL LEAK",
            "CONTAMINATED_TAG": "CONTAMINATED", "POSITIVE_READ_ERROR_TAG": "Positive Read Error",
            "RANGE_ERROR_TAG": "Range Error",
            "NEGATIVE_READ_ERROR_TAG": "Negative ReadError", # Reverted to be consistent
            "PHYSICALLY_DAMAGED_TAG": "Physically Damaged", "DRIFTING_TAG": "DRIFTING",
            "CLEANED_TAG": "Cleaned"
        }
        for key, name in tag_map.items():
            gids = self.find_gids_by_name(all_tags, name)
            if not gids:
                logging.warning(f"Configuration Warning: Tag '{name}' not found in Asana.")
                self.gids[key] = [] if key.endswith('S') else None
            else:
                self.gids[key] = gids if key.endswith('S') else gids[0]

        user_map = {
            "SUSAN_HEARON_USER": "Susan Hearon",
            "SHARED_SUBTASK_ASSIGNEE": "Michelle Hughes",
            "ACCOUNT_MANAGER_ASSIGNEE": "Mandy McIntosh"
        }
        for key, name in user_map.items():
            gids = self.find_gids_by_name(all_users, name)
            if not gids:
                logging.warning(f"Configuration Warning: User '{name}' not found in Asana.")
                self.gids[key] = None
            else:
                self.gids[key] = gids[0]

        return critical_errors