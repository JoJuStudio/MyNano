import curses
import sys
import time

def draw_title_bar(stdscr, filename, dirty, cursor_y, cursor_x):
    """Draws the top title bar with time, filename, and cursor position."""
    h, w = stdscr.getmaxyx()
    time_str = time.strftime("%H:%M:%S")
    title = f"🕒 {time_str} | 📄 {filename or 'Untitled'}{' *' if dirty else ''} | 📏 Ln {cursor_y + 1}, Col {cursor_x + 1}"
    
    # Truncate title to window width
    truncated_title = title[:w-1]
    fill = ' ' * (w - 1 - len(truncated_title))
    
    stdscr.attron(curses.A_REVERSE)
    stdscr.addstr(0, 0, truncated_title)
    if fill:
        stdscr.addstr(0, len(truncated_title), fill)
    stdscr.attroff(curses.A_REVERSE)

def draw_status_bar(stdscr, message):
    """Draws the bottom status bar with messages."""
    h, w = stdscr.getmaxyx()
    if h < 2:
        return
    
    # Truncate message to window width
    truncated_msg = message[:w-1]
    fill = ' ' * (w - 1 - len(truncated_msg))
    
    stdscr.attron(curses.A_REVERSE)
    stdscr.addstr(h-1, 0, truncated_msg)
    if fill:
        stdscr.addstr(h-1, len(truncated_msg), fill)
    stdscr.attroff(curses.A_REVERSE)

def save_file_dialog(stdscr, filename):
    """Opens a save dialog at the bottom for entering a filename."""
    h, w = stdscr.getmaxyx()
    if h < 3:
        return None
    
    prompt = "Save as: "
    stdscr.addstr(h-2, 0, prompt)
    max_len = w - len(prompt) - 1
    
    curses.echo()
    try:
        new_filename = stdscr.getstr(h-2, len(prompt), max_len).decode("utf-8").strip()
    except curses.error:
        new_filename = ""
    curses.noecho()

    return new_filename or filename

def insert_text(buffer, cursor_y, cursor_x, text):
    """Inserts pasted text safely at the cursor position."""
    lines = text.split("\n")
    
    # Handle first line
    while cursor_y >= len(buffer):
        buffer.append("")
    buffer[cursor_y] = buffer[cursor_y][:cursor_x] + lines[0] + buffer[cursor_y][cursor_x:]
    
    # Insert remaining lines
    new_cursor_y = cursor_y
    new_cursor_x = cursor_x + len(lines[0])
    for line in lines[1:]:
        new_cursor_y += 1
        buffer.insert(new_cursor_y, line)
        new_cursor_x = len(line)
    
    return new_cursor_y, new_cursor_x

def main(stdscr, filename=None):
    curses.curs_set(1)
    stdscr.clear()
    curses.use_default_colors()
    stdscr.timeout(100)

    buffer = [""]
    cursor_y = 0
    cursor_x = 0
    scroll_offset = 0
    dirty = False
    status_message = "Ctrl+X: Exit | Ctrl+O: Save | Ctrl+V: Paste"

    if filename:
        try:
            with open(filename, 'r') as f:
                buffer = f.read().splitlines() or [""]
        except FileNotFoundError:
            status_message = "⚠️ File not found. Created new file."
        except Exception as e:
            status_message = f"⚠️ Error opening file: {str(e)}"

    while True:
        h, w = stdscr.getmaxyx()
        stdscr.clear()
        
        # Handle minimum window size
        if h < 3 or w < 10:
            stdscr.addstr(0, 0, "Window too small!")
            stdscr.refresh()
            continue
        
        # Adjust scroll offset
        visible_lines = h - 2
        if cursor_y < scroll_offset:
            scroll_offset = cursor_y
        elif cursor_y >= scroll_offset + visible_lines:
            scroll_offset = cursor_y - visible_lines + 1
        
        draw_title_bar(stdscr, filename, dirty, cursor_y, cursor_x)
        draw_status_bar(stdscr, status_message)
        
        # Display visible buffer lines
        for i in range(visible_lines):
            line_num = scroll_offset + i
            if line_num < len(buffer):
                stdscr.addstr(i + 1, 0, buffer[line_num][:w-1])
        
        # Update cursor position
        try:
            stdscr.move(1 + cursor_y - scroll_offset, min(cursor_x, w-1))
        except curses.error:
            pass
        
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == -1:
            continue
        
        # Handle controls
        if key == 24:  # Ctrl+X
            if dirty:
                status_message = "⚠️ Unsaved changes! Press Ctrl+X again to exit."
                dirty = False
            else:
                break
        elif key == 15:  # Ctrl+O (Save)
            new_filename = save_file_dialog(stdscr, filename)
            if new_filename:
                try:
                    with open(new_filename, 'w') as f:
                        f.write('\n'.join(buffer))
                    filename = new_filename
                    dirty = False
                    status_message = f"💾 Saved: {filename}"
                except Exception as e:
                    status_message = f"⚠️ Save failed: {str(e)}"
        elif key in (curses.KEY_BACKSPACE, 127, 8):  # Backspace
            if cursor_x > 0:
                buffer[cursor_y] = buffer[cursor_y][:cursor_x-1] + buffer[cursor_y][cursor_x:]
                cursor_x -= 1
                dirty = True
            elif cursor_y > 0:
                prev_len = len(buffer[cursor_y-1])
                buffer[cursor_y-1] += buffer.pop(cursor_y)
                cursor_y -= 1
                cursor_x = prev_len
                dirty = True
        elif key in (curses.KEY_ENTER, 10, 13):  # Enter
            new_line = buffer[cursor_y][cursor_x:]
            buffer[cursor_y] = buffer[cursor_y][:cursor_x]
            buffer.insert(cursor_y + 1, new_line)
            cursor_y += 1
            cursor_x = 0
            dirty = True
        elif key == curses.KEY_UP and cursor_y > 0:
            cursor_y -= 1
            cursor_x = min(cursor_x, len(buffer[cursor_y]))
        elif key == curses.KEY_DOWN and cursor_y < len(buffer) - 1:
            cursor_y += 1
            cursor_x = min(cursor_x, len(buffer[cursor_y]))
        elif key == curses.KEY_LEFT and cursor_x > 0:
            cursor_x -= 1
        elif key == curses.KEY_RIGHT and cursor_x < len(buffer[cursor_y]):
            cursor_x += 1
        elif key == 22:  # Ctrl+V (Paste)
            # Fast paste implementation
            curses.cbreak()
            curses.raw()
            stdscr.nodelay(True)
            curses.flushinp()
            
            pasted = []
            try:
                stdscr.addstr(h-2, 0, "📋 Pasting... (ESC to cancel)")
                stdscr.clrtoeol()
                stdscr.refresh()
                
                while True:
                    k = stdscr.getch()
                    if k == -1:
                        break
                    if k == 27:  # ESC
                        pasted = []
                        break
                    try:
                        pasted.append(chr(k))
                    except ValueError:
                        pass
                    
                    # Update progress every 200 chars
                    if len(pasted) % 200 == 0:
                        stdscr.addstr(h-2, 0, f"📋 Pasting... {len(pasted)} chars")
                        stdscr.clrtoeol()
                        stdscr.refresh()
            finally:
                stdscr.nodelay(False)
                curses.noraw()
                curses.nocbreak()
            
            if pasted:
                pasted_text = ''.join(pasted)
                cursor_y, cursor_x = insert_text(buffer, cursor_y, cursor_x, pasted_text)
                dirty = True
                status_message = f"📋 Pasted {len(pasted_text)} chars!"
            else:
                status_message = "⚠️ Paste canceled."
        elif 32 <= key <= 126:  # Printable chars
            buffer[cursor_y] = buffer[cursor_y][:cursor_x] + chr(key) + buffer[cursor_y][cursor_x:]
            cursor_x += 1
            dirty = True

if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else None
    curses.wrapper(main, filename)