# ui_components.py (v2.2)
import streamlit as st

def cor_dog_reason_selector():
    """
    Displays the UI for selecting a reason and adding an optional comment.
    The details text box is no longer autofilled.
    """
    reasons = [
        "Bad Sensor", "Pressure Oscillation", "INTERNAL LEAK",
        "CONTAMINATED", "Positive Read Error", "Range Error",
        "Negative ReadError", "Physically Damaged", "DRIFTING", "OTHER"
    ]
    
    st.subheader("Select Reason")
    
    # Dropdown for predefined reasons
    selected_reason = st.selectbox(
        "Common Issues:", 
        reasons, 
        key="reason_selector"
    )
    
    # Text box for optional details is now empty by default
    details_text = st.text_input("Optional Details:", help="Add any extra context here.")
    
    final_comment = ""
    tag_name_to_add = None
    
    if selected_reason == "OTHER":
        # For OTHER, the comment is whatever the user typed, or just "OTHER"
        final_comment = f"AUTO: {details_text}" if details_text else "AUTO: OTHER"
        tag_name_to_add = None # No specific tag for OTHER
    else:
        # For standard reasons, combine the reason and any optional details
        if details_text:
            final_comment = f"AUTO: {selected_reason} - {details_text}"
        else:
            final_comment = f"AUTO: {selected_reason}"
        tag_name_to_add = selected_reason
            
    return {"comment": final_comment, "tag_name_to_add": tag_name_to_add}