# camera_component.py (v2.14)
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from pyzbar.pyzbar import decode
import av

def barcode_scanner_component(key: str):
    """
    Creates a scanner instance that uses a unique key to manage its state.
    Returns the scanned value when a barcode is detected.
    """
    # We use a unique session state key to store the scanned value
    session_key = f"scanned_value_{key}"

    def video_frame_callback(frame: av.VideoFrame):
        img = frame.to_ndarray(format="bgr24")
        decoded_objects = decode(img)
        if decoded_objects:
            # Set the value in session state
            st.session_state[session_key] = decoded_objects[0].data.decode("utf-8")
        return frame

    webrtc_streamer(
        key=key,
        mode=WebRtcMode.SENDRECV,
        video_frame_callback=video_frame_callback,
        media_stream_constraints={"video": True, "audio": False},
        async_processing=True,
    )

    # Check if a value was found and return it
    if session_key in st.session_state and st.session_state[session_key]:
        result = st.session_state[session_key]
        # Clean up the session state
        del st.session_state[session_key]
        return result
        
    return None