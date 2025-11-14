
import sys

def print_and_erase(text):
    """Prints text to the console and erases the line."""
    sys.stdout.write('\r' + text)
    sys.stdout.flush()

