import os

def rename_csv(path, old_text, new_text):
    folder = os.path.dirname(path)
    filename = os.path.basename(path)

    # If old_text is not found → skip
    if old_text not in filename:
        return False, filename  # Not renamed

    # Replace user-specified text
    new_name = filename.replace(old_text, new_text)

    # Build full new path
    new_path = os.path.join(folder, new_name)

    # Rename file
    os.rename(path, new_path)

    return True, new_name  # Renamed successfully


def main():
    folder = input("Enter folder path: ").strip()

    old_text = input("Enter the text you want to replace: ").strip()
    new_text = input("Enter the new text to insert: ").strip()

    renamed_count = 0
    error_count = 0

    for f in os.listdir(folder):
        if f.lower().endswith(".csv"):
            full_path = os.path.join(folder, f)
            renamed, result = rename_csv(full_path, old_text, new_text)

            if renamed:
                print(f"✔ Renamed: {f} → {result}")
                renamed_count += 1
            else:
                print(f"✖ No match in: {f}")
                error_count += 1

    print("\n===== SUMMARY =====")
    print(f"Files renamed: {renamed_count}")
    print(f"Files skipped (no match): {error_count}")
    print("===================")


if __name__ == "__main__":
    main()
