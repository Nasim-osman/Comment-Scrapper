import os
import re
import json
from datetime import datetime, timezone
import dateparser
import pandas as pd
from typing import List, Dict, Any
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

EXPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "exports"))
os.makedirs(EXPORTS_DIR, exist_ok=True)

def normalize_timestamp(val: Any) -> str:
    """Normalizes any timestamp, epoch, or relative string into a formatted YYYY-MM-DD HH:MM:SS string."""
    if not val or str(val).strip() in ["", "-", "None"]:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = str(val).strip()
    try:
        f = float(s)
        if f > 1000000000:
            return datetime.fromtimestamp(f, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    if "T" in s:
        cleaned_s = s.replace("Z", "").split(".")[0]
        try:
            dt = datetime.fromisoformat(cleaned_s)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    try:
        dt = dateparser.parse(s)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return s

def comments_to_dataframe(comments: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Converts comments to a DataFrame with EXACTLY the 6 columns requested:
    [Type, Author, Comment, Replying_To, Likes, Published_At]
    """
    if not comments:
        return pd.DataFrame(columns=["Type", "Author", "Comment", "Replying_To", "Likes", "Published_At"])
    
    # Pre-pass: map comment IDs to authors for accurate parent author lookup
    id_to_author = {}
    for c in comments:
        cid = c.get("id") or c.get("cid") or c.get("comment_id")
        auth = c.get("author") or c.get("Author") or ""
        if cid and auth:
            id_to_author[str(cid)] = auth

    rows = []
    for c in comments:
        # 1. Type: "MAIN COMMENT" or "REPLY"
        raw_type = c.get("Type") or c.get("type")
        if raw_type and str(raw_type).strip().upper() in ["MAIN COMMENT", "REPLY"]:
            comment_type = str(raw_type).strip().upper()
        else:
            is_reply = bool(c.get("is_reply", False))
            comment_type = "REPLY" if is_reply else "MAIN COMMENT"

        # 2. Author
        author = c.get("Author") or c.get("author") or "Anonymous"

        # 3. Comment Text
        comment_text = c.get("Comment")
        if comment_text is None:
            comment_text = c.get("text")
        if comment_text is None:
            comment_text = c.get("cleaned_text", "")
        comment_text = str(comment_text)

        # 4. Replying_To
        replying_to = "-"
        if comment_type == "REPLY":
            custom_reply = c.get("Replying_To") or c.get("replying_to")
            if custom_reply and str(custom_reply).strip() != "-":
                replying_to = str(custom_reply).strip()
            elif c.get("parent_id") and str(c.get("parent_id")) in id_to_author:
                replying_to = id_to_author[str(c.get("parent_id"))]
            else:
                # Check if the comment text begins with an @mention (e.g. "@oxfordnoi5609 Thanks...")
                match = re.match(r"^(@[a-zA-Z0-9_\.\-]+)", comment_text.strip())
                if match:
                    replying_to = match.group(1)
                else:
                    replying_to = "-"
        else:
            replying_to = "-"

        # 5. Likes
        raw_likes = c.get("Likes") if c.get("Likes") is not None else c.get("likes", 0)
        try:
            likes = int(str(raw_likes).replace(",", "").strip())
        except Exception:
            likes = 0

        # 6. Published_At
        pub_at = (
            c.get("Published_At")
            or c.get("published_at")
            or c.get("timestamp")
            or c.get("time")
            or c.get("created_at")
            or ""
        )
        clean_pub_at = normalize_timestamp(pub_at)

        rows.append({
            "Type": comment_type,
            "Author": author,
            "Comment": comment_text,
            "Replying_To": replying_to,
            "Likes": likes,
            "Published_At": clean_pub_at
        })

    return pd.DataFrame(rows, columns=["Type", "Author", "Comment", "Replying_To", "Likes", "Published_At"])

def export_to_csv(comments: List[Dict[str, Any]], filename_prefix: str = "comments") -> str:
    """
    Exports comments to CSV with utf-8-sig encoding (BOM),
    with the exact columns: Type, Author, Comment, Replying_To, Likes, Published_At.
    """
    df = comments_to_dataframe(comments)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp_str}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    return filepath

def export_to_excel(comments: List[Dict[str, Any]], filename_prefix: str = "comments") -> str:
    """
    Exports comments to a beautifully formatted Microsoft Excel file (.xlsx)
    with the exact columns: Type, Author, Comment, Replying_To, Likes, Published_At.
    """
    df = comments_to_dataframe(comments)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp_str}.xlsx"
    filepath = os.path.join(EXPORTS_DIR, filename)
    
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Comments_Dataset", index=False)
        worksheet = writer.sheets["Comments_Dataset"]
        
        # Style Header Row
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )
        
        for col_idx in range(1, len(df.columns) + 1):
            cell = worksheet.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = thin_border
            
        # Specific column widths
        col_widths = {
            "Type": 16,
            "Author": 24,
            "Comment": 65,
            "Replying_To": 22,
            "Likes": 12,
            "Published_At": 24
        }
        
        for col in worksheet.columns:
            col_letter = get_column_letter(col[0].column)
            col_name = str(col[0].value) if col[0].value else ""
            worksheet.column_dimensions[col_letter].width = col_widths.get(col_name, 20)
            
            # Align cells
            for cell in col[1:]:
                if col_name == "Comment":
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                elif col_name == "Likes":
                    cell.alignment = Alignment(horizontal="right", vertical="top")
                elif col_name in ["Type", "Published_At"]:
                    cell.alignment = Alignment(horizontal="center", vertical="top")
                else:
                    cell.alignment = Alignment(vertical="top")
                    
        # Freeze top row
        worksheet.freeze_panes = "A2"
        
    return filepath

def export_to_json(comments: List[Dict[str, Any]], filename_prefix: str = "comments") -> str:
    """Exports comments to structured UTF-8 JSON file using the standard schema."""
    df = comments_to_dataframe(comments)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix}_{timestamp_str}.json"
    filepath = os.path.join(EXPORTS_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)
        
    return filepath
