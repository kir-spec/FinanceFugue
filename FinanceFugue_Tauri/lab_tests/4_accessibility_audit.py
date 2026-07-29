import re
import os

HTML_PATH = "e:/coding/client_manager/FinanceFugue_Tauri/index.html"

def run_accessibility_audit():
    print(f"============================================================")
    print(f"          IT LAB: UX & ACCESSIBILITY AUDIT                  ")
    print(f"============================================================")
    
    if not os.path.exists(HTML_PATH):
        print(f"[-] {HTML_PATH} not found. Cannot perform audit.")
        return

    with open(HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Heuristics
    buttons = re.findall(r'<button[^>]*>', content)
    inputs = re.findall(r'<input[^>]*>', content)
    
    print(f"[*] Found {len(buttons)} <button> elements and {len(inputs)} <input> elements.")
    
    # 1. Keyboard Navigation (tabindex or native focusable elements)
    # Buttons and inputs are natively focusable, but we check if any divs have onclick without tabindex
    clickable_divs = re.findall(r'<div[^>]*onclick[^>]*>', content)
    bad_divs = [div for div in clickable_divs if 'tabindex' not in div]
    
    print("\n[*] Checking Keyboard Navigation (Keyboard Traps & Focusable Elements)...")
    if bad_divs:
        print(f"[-] WARNING: Found {len(bad_divs)} clickable <div> elements missing 'tabindex'.")
        print("    This prevents keyboard-only users from accessing these functions.")
    else:
        print("[+] PASS: No non-focusable clickable divs found.")

    # 2. Screen Reader Support (aria-labels on icon-only buttons)
    print("\n[*] Checking Screen Reader Compatibility (ARIA & Alt text)...")
    # A simple heuristic: check if buttons contain text or aria-labels
    icon_buttons_without_aria = 0
    for btn in buttons:
        # If it doesn't have aria-label and has a class usually associated with icons
        if 'aria-label' not in btn and ('icon' in btn or 'fas' in btn or 'material-symbols' in btn):
            icon_buttons_without_aria += 1

    if icon_buttons_without_aria > 0:
        print(f"[-] WARNING: Found {icon_buttons_without_aria} icon buttons missing 'aria-label'.")
    else:
        print("[+] PASS: Accessible labels found for interactive elements.")
        
    print("\n[*] Accessibility Audit Complete.")

if __name__ == "__main__":
    run_accessibility_audit()
