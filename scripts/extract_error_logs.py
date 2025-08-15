
import os

def extract_error_context(log_dir, output_file):
    """
    Extracts lines containing 'error' and their surrounding context from log files.

    Args:
        log_dir (str): The path to the directory containing log files.
        output_file (str): The path to the file where the output will be written.
    """
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for filename in os.listdir(log_dir):
            if os.path.isfile(os.path.join(log_dir, filename)):
                out_f.write(f"--- Errors from {filename} ---
")
                try:
                    with open(os.path.join(log_dir, filename), 'r', encoding='utf-8') as in_f:
                        lines = in_f.readlines()
                        for i, line in enumerate(lines):
                            if 'error' in line.lower():
                                # Write the line before, the error line, and the line after
                                if i > 0:
                                    out_f.write(lines[i-1])
                                out_f.write(line)
                                if i < len(lines) - 1:
                                    out_f.write(lines[i+1])
                                out_f.write("-" * 20 + "\n")
                except UnicodeDecodeError:
                    out_f.write(f"Could not read file {filename} due to encoding issues.
")
                except Exception as e:
                    out_f.write(f"An error occurred while processing {filename}: {e}
")

if __name__ == "__main__":
    # Assuming the script is in the 'scripts' directory, and logs are in the 'logs' directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    log_directory = os.path.join(current_dir, '..', 'logs')
    output_log_file = os.path.join(current_dir, '..', 'extracted_errors.log')

    if not os.path.exists(log_directory):
        print(f"Log directory not found at: {log_directory}")
    else:
        extract_error_context(log_directory, output_log_file)
        print(f"Error logs extracted to: {output_log_file}")
