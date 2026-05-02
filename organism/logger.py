import traceback
import sys
from .models import NeuralError
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def log_neural_error(exception, context=None):
    """
    Captures an exception, logs it to the database, and alerts the UI.
    """
    error_type = type(exception).__name__
    message = str(exception)
    stack_trace = "".join(traceback.format_exception(*sys.exc_info()))
    
    # Save to DB
    try:
        NeuralError.objects.create(
            error_type=error_type,
            message=message,
            stack_trace=stack_trace,
            context=context
        )
        print(f"[🚨 NEURAL ERROR]: {error_type}: {message}")
    except Exception as e:
        print(f"[CRITICAL FAILURE] Could not even log the error: {e}")

    # Alert the UI via WebSocket if possible
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                "rad_comm",
                {
                    "type": "rad_status_event",
                    "content": f"🚨 NEURAL GLITCH DETECTED: {error_type}"
                }
            )
    except:
        pass
