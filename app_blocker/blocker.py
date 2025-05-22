import psutil
import datetime
import os
import threading
import time

def monitor_loop(
    app_path_val, 
    end_hour_val, 
    end_minute_val, 
    stop_event,
    get_block_state_func, # Expected to return (block_activated_today, date_block_activated)
    set_block_state_func, # Expected to take (block_activated_today, date_block_activated) and save config
    log_status_func,
    call_after_func,      # For thread-safe calls to GUI or other main-thread functions
    on_monitoring_stopped_func # Callback to inform GUI that monitoring has actually stopped
):
    """
    Monitors the specified application and blocks it after the designated time.
    This function is intended to be run in a separate thread.
    """
    target_app_full_path = app_path_val
    if not target_app_full_path:
        log_status_func("Critical Error: Target application path missing in monitor_loop.")
        if on_monitoring_stopped_func: # Ensure GUI knows we stopped due to error
             call_after_func(on_monitoring_stopped_func)
        return

    target_app_name = os.path.basename(target_app_full_path).lower()
    last_status_message = ""

    log_status_func(f"Monitoring thread will observe {target_app_name}. Block after {end_hour_val:02d}:{end_minute_val:02d}.")

    while not stop_event.is_set():
        try:
            current_time = datetime.datetime.now()
            current_date = current_time.date()
            # These values (end_hour_val, end_minute_val) are fixed when the thread starts.
            # If they need to be dynamic, they'd have to be fetched via a callback too.
            end_time_today = current_time.replace(hour=end_hour_val, minute=end_minute_val, second=0, microsecond=0)

            block_activated_today, date_block_activated = get_block_state_func()

            # --- Daily Reset Logic ---
            if block_activated_today and date_block_activated and current_date > date_block_activated:
                log_status_func(f"New day ({current_date}). Resetting block for {target_app_name}.")
                block_activated_today = False
                date_block_activated = None 
                set_block_state_func(block_activated_today, date_block_activated) # This call should handle saving the config.
                last_status_message = "" 

            # --- Block Activation Logic ---
            if not block_activated_today and current_time >= end_time_today:
                log_status_func(f"End time {end_time_today.strftime('%H:%M')} reached. Activating block for {target_app_name}.")
                block_activated_today = True
                date_block_activated = current_date
                set_block_state_func(block_activated_today, date_block_activated) # This call should handle saving the config.
                last_status_message = ""

            # --- Process Killing Logic ---
            if block_activated_today:
                current_message = f"Blocking {target_app_name}. Access denied until tomorrow."
                if current_message != last_status_message:
                    log_status_func(current_message)
                    last_status_message = current_message

                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        proc_exe = proc.info.get('exe')
                        if proc_exe and os.path.normcase(proc_exe) == os.path.normcase(target_app_full_path):
                            log_status_func(f"Found running instance of {target_app_name} (PID: {proc.pid}). Terminating...")
                            proc.terminate()
                            try:
                                proc.wait(timeout=1) # Wait for graceful termination
                            except psutil.TimeoutExpired:
                                log_status_func(f"Force killing {target_app_name} (PID: {proc.pid}) after timeout.")
                                proc.kill() # Force kill if terminate didn't work
                            log_status_func(f"{target_app_name} (PID: {proc.pid}) terminated.")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        # Process might have terminated, or we don't have permissions.
                        # LogAccessDenied if it's frequent and unexpected.
                        pass 
                    except Exception as e_proc:
                        proc_name_str = "unknown_process"
                        try:
                            proc_name_str = proc.name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                             pass # Can't get name, use default
                        log_status_func(f"Error checking/terminating '{proc_name_str}' (PID: {proc.pid if proc else 'N/A'}): {e_proc}")
            else: # Not blocked yet for today
                current_message = f"Monitoring {target_app_name}. Allowed until {end_time_today.strftime('%H:%M')}."
                if current_message != last_status_message:
                    log_status_func(current_message)
                    last_status_message = current_message
        
        except Exception as e_loop:
            log_status_func(f"Major error in monitoring loop: {e_loop}. Loop will attempt to continue.")
            last_status_message = "" # Reset message to ensure it re-logs after error
            # Consider adding a small delay here if errors are rapid.
            time.sleep(5) # Wait 5 seconds after a major error to prevent tight error loops

        # Wait for the stop event or timeout. Check more frequently for responsiveness.
        stop_event.wait(timeout=1.0) 

    log_status_func(f"Monitoring thread for {target_app_name} has gracefully stopped.")
    if on_monitoring_stopped_func: # Ensure GUI knows we stopped
        call_after_func(on_monitoring_stopped_func)
