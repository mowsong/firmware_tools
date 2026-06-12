import time
import math
import random
import argparse
import serial

def get_formats():
    """Returns a dictionary of available data formats and their descriptions."""
    return {
        "single_int": "A single integer per line (e.g., '123\\n').",
        "single_float": "A single float per line (e.g., '45.67\\n').",
        "multi_int": "Two integers separated by a comma (e.g., '10,20\\n').",
        "multi_float": "Two floats separated by a comma (e.g., '1.23,4.56\\n').",
        "single_int_single_float": "An integer and a float separated by a space (e.g., '42 3.14\\n').",
        "sine_cosine": "Sine and cosine waves with labels (e.g., 'S:0.50, C:0.87\\n').",
        "mixed_delim": "Three values with mixed delimiters (e.g., 'X:10 Y:20.5;Z:30\\n').",
        "random_walk": "Three random walk series with labels (e.g., 'A:5, B:15, C:25\\n')."
    }

def generate_data(format_name, counter):
    """Generates a line of data based on the selected format."""
    if format_name == "single_int":
        # Simple counter
        return f"{counter % 256}\n"
    
    elif format_name == "single_float":
        # A sine wave
        val = 5 * math.sin(counter * 0.1)
        return f"{val:.4f}\n"

    elif format_name == "multi_int":
        # Two counters with different speeds
        val1 = counter % 100
        val2 = 50 + (counter // 2) % 50
        return f"{val1},{val2}\n"

    elif format_name == "multi_float":
        # Sine and a ramp
        val1 = 10 * math.sin(counter * 0.1)
        val2 = (counter % 100) / 10.0
        return f"{val1:.4f},{val2:.4f}\n"

    elif format_name == "sine_cosine":
        # Classic sine/cosine waves
        angle = counter * 0.05
        val1 = math.sin(angle)
        val2 = math.cos(angle)
        return f"S:{val1:.2f}, C:{val2:.2f}\n"

    elif format_name == "mixed_delim":
        # Uses space, colon, and semicolon delimiters
        val1 = counter % 50
        val2 = 25 + 25 * math.sin(counter * 0.2)
        val3 = random.randint(-10, 10)
        # Note the semicolon as a dataset delimiter
        return f"X:{val1} Y:{val2:.2f};Z:{val3}\n"
    
    elif format_name == "single_int_single_float":
        # A single integer and a single float separated by a space
        val1 = counter % 100
        val2 = 10 * math.cos(counter * 0.1)
        return f"{val1} {val2:.4f}\n"

    elif format_name == "random_walk":
        # Three independent random walks
        # Use global variables to maintain state across calls
        global walk_a, walk_b, walk_c
        walk_a += random.uniform(-1.5, 1.5)
        walk_b += random.uniform(-1.0, 1.0)
        walk_c += random.uniform(-0.5, 0.5)
        # Keep them roughly centered
        if not -50 < walk_a < 50: walk_a = 0
        if not -50 < walk_b < 50: walk_b = 0
        if not -50 < walk_c < 50: walk_c = 0
        return f"A:{walk_a:.2f}, B:{walk_b:.2f}, C:{walk_c:.2f}\n"

    else:
        return f"Unknown format: {format_name}\n"

def main():
    formats = get_formats()
    parser = argparse.ArgumentParser(
        description="Serial Device Simulator. Sends various data formats over a serial port.",
        formatter_class=argparse.RawTextHelpFormatter # To preserve newlines in help text
    )
    parser.add_argument("port", help="The serial port to use (e.g., COM10).")
    parser.add_argument("--baud", type=int, default=19200, help="Baud rate (default: 19200).")
    parser.add_argument("--format", choices=formats.keys(), default="sine_cosine",
                        help="Data format to send.\nAvailable formats:\n" +
                             "\n".join([f"  {k}: {v}" for k, v in formats.items()]) +
                             "\n(default: %(default)s)")
    parser.add_argument("--interval", type=float, default=0.1, help="Time interval between sends in seconds (default: 0.1).")

    args = parser.parse_args()

    print(f"Starting simulator on {args.port} at {args.baud} baud.")
    print(f"Sending format: '{args.format}' every {args.interval} seconds.")
    print("Press Ctrl+C to stop.")

    try:
        with serial.Serial(args.port, args.baud, timeout=1) as ser:
            counter = 0
            while True:
                data_line = generate_data(args.format, counter)
                ser.write(data_line.encode('ascii'))
                print(f"Sent: {data_line.strip()}", end='\r')
                time.sleep(args.interval)
                counter += 1

    except serial.SerialException as e:
        print(f"\nError: Could not open port {args.port}.")
        print(f"Details: {e}")
        print("Please ensure the port is correct and not in use by another application.")
        print("If using virtual ports, make sure the pair is correctly configured and linked.")
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    # Globals for the random_walk format
    walk_a, walk_b, walk_c = 0, 0, 0
    main()
