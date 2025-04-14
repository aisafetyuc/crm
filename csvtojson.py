import csv
import json
import os
import re
import io

def simplify_question(question):
    """Create a simplified version of an essay question."""
    # Remove emojis and other special characters
    emojis = ["👤", "✉️", "📲", "🎓", "👋", "🤔", "👩‍💻", "💬", "📝", "🤖", "🙌"]
    
    # Remove emojis
    for emoji in emojis:
        question = question.replace(emoji, "")
    
    # Clean up the question
    question = question.strip()
    
    # Truncate if too long
    if len(question) > 30:
        words = question.split()
        shortened = []
        total_length = 0
        
        for word in words:
            if total_length + len(word) <= 25:
                shortened.append(word)
                total_length += len(word) + 1  # +1 for space
            else:
                break
        
        question = " ".join(shortened)
        
        # If we truncated, add ellipsis
        if len(shortened) < len(words):
            question += "..."
    
    # Replace spaces and special chars
    question = re.sub(r'[^\w\s]', '', question)  # Remove special characters
    question = re.sub(r'\s+', '_', question)     # Replace spaces with underscores
    
    return question.lower()

def read_csv_file(filename):
    """Read a CSV file and extract all data including essay responses."""
    try:
        # Read the entire file but filter out lines that are just commas
        with open(filename, 'r', encoding='utf-8') as f:
            lines = []
            for line in f:
                # Skip lines that are just commas
                if line.strip().replace(',', '') == '':
                    continue
                lines.append(line)
        
        # Process the filtered CSV data
        csv_data = io.StringIO(''.join(lines))
        reader = csv.DictReader(csv_data)
        
        # Contact info patterns to identify contact columns
        contact_patterns = {
            "nombre": ["Nombre", "👤", "Nombre Completo", "Nombre completo"],
            "correo": ["Correo", "✉️", "Correo UC", "Dirección de correo electrónico"],
            "telegram": ["Telegram", "📲"],
            "carrera": ["Carrera", "Grado", "🎓", "Carrera/Grado"],
            "generacion": ["Generación", "Generacion", "👋"]
        }
        
        # Find contact info columns
        contact_columns = set()
        contact_mapping = {}
        for category, patterns in contact_patterns.items():
            for col in reader.fieldnames:
                if any(pattern in col for pattern in patterns):
                    contact_columns.add(col)
                    contact_mapping[category] = col
                    break
        
        # Skip certain administrative columns
        admin_patterns = [
            "marca temporal", "estado", "prioridad", "puntuación", 
            "observaciones", "salvageable", "razones", "promedio", "notas", "preferencia",
            "dirección de correo electrónico" # This is handled as correo
        ]
        
        admin_columns = set(col for col in reader.fieldnames 
                          if any(pattern in col.lower() for pattern in admin_patterns))
        
        # Get base filename without directory
        base_filename = os.path.basename(filename)
        
        result = []
        for row in reader:
            person = {}
            
            # Extract contact info
            for category, col in contact_mapping.items():
                if col in row:
                    value = row[col].strip() if row[col] else ""
                    
                    # Special handling for telegram handles
                    if category == "telegram" and value:
                        # Check for common "no telegram" indicators
                        no_telegram_indicators = ["no tengo", "no", "none", "0", "n/a", "-"]
                        if any(value.lower().strip() == indicator for indicator in no_telegram_indicators):
                            value = ""
                        else:
                            # Remove all spaces
                            value = value.replace(" ", "")
                            # Ensure it starts with @
                            if not value.startswith("@"):
                                value = "@" + value
                    
                    person[category] = value
                else:
                    person[category] = ""
            
            # Extract essay responses (all non-contact, non-admin columns)
            essay_responses = {}
            for col in reader.fieldnames:
                if col in contact_columns or col in admin_columns:
                    continue
                
                # Create a shortened version of the question
                short_question = simplify_question(col)
                
                # Add essay response if not empty
                if col in row and row[col]:
                    essay_responses[short_question] = row[col].strip()
            
            # Add form metadata
            person["form"] = base_filename
            person["essay_responses"] = essay_responses
            person["source"] = filename
            
            result.append(person)
        
        return result
    except Exception as e:
        print(f"Error reading {filename}: {str(e)}")
        return []

def process_csv_files(filenames):
    """Process multiple CSV files and combine data with postulaciones."""
    all_people = []
    
    for filename in filenames:
        people = read_csv_file(filename)
        all_people.extend(people)
    
    # Filter out entries with no name, no email, and no telegram
    filtered_people = []
    filtered_count = 0
    
    for person in all_people:
        email = person.get("correo", "").strip()
        nombre = person.get("nombre", "").strip()
        telegram = person.get("telegram", "").strip()
        
        if email or nombre or telegram:
            # Add normalized name for consistency
            if nombre:
                person["nombre_normalized"] = normalize_spanish_name(nombre)
            filtered_people.append(person)
        else:
            filtered_count += 1
    
    if filtered_count > 0:
        print(f"Filtered out {filtered_count} entries with no name, no email, and no telegram")
    
    # Group people by email
    email_groups = {}
    
    for person in filtered_people:
        email = person.get("correo", "").strip().lower()
        
        if email:
            if email not in email_groups:
                email_groups[email] = []
            email_groups[email].append(person)
        else:
            # For people without email, create a unique key based on their name+telegram
            name = person.get("nombre_normalized", person.get("nombre", "")).strip().lower()
            telegram = person.get("telegram", "").strip().lower()
            key = f"no_email_{name}_{telegram}"
            
            if key not in email_groups:
                email_groups[key] = []
            email_groups[key].append(person)
    
    # Process each group
    result = []
    
    for _, group in email_groups.items():
        # Start with first person's contact info
        merged = {
            "nombre": group[0].get("nombre", ""),
            "nombre_normalized": group[0].get("nombre_normalized", normalize_spanish_name(group[0].get("nombre", ""))),
            "correo": group[0].get("correo", ""),
            "telegram": group[0].get("telegram", ""),
            "carrera": group[0].get("carrera", ""),
            "generacion": group[0].get("generacion", ""),
            "postulaciones": [],
            "sources": []
        }
        
        # Find best contact info across the group
        for person in group:
            for field in ["nombre", "correo", "telegram", "carrera", "generacion"]:
                current = merged.get(field, "")
                new_value = person.get(field, "")
                
                # Ensure telegram format consistency
                if field == "telegram" and new_value:
                    # Check for common "no telegram" indicators
                    no_telegram_indicators = ["no tengo", "no", "none", "0", "n/a", "-"]
                    if any(new_value.lower().strip() == indicator for indicator in no_telegram_indicators):
                        new_value = ""
                    else:
                        # Remove all spaces
                        new_value = new_value.replace(" ", "")
                        if not new_value.startswith("@"):
                            new_value = "@" + new_value
                
                if not current and new_value:
                    merged[field] = new_value
                elif current and new_value and len(new_value) > len(current):
                    merged[field] = new_value
        
        # Add all postulaciones
        for person in group:
            # Get just the filename without path
            form_filename = os.path.basename(person.get("source", "unknown"))
            
            # Create postulacion entry
            postulacion = {
                "form": form_filename
            }
            
            # Add essay responses
            for question, answer in person.get("essay_responses", {}).items():
                postulacion[question] = answer
            
            # Only add if there are actual essay responses
            if len(postulacion) > 1:  # More than just the "form" field
                merged["postulaciones"].append(postulacion)
            
            # Track source
            if "source" in person:
                merged["sources"].append(person["source"])
        
        # Remove duplicate sources
        merged["sources"] = list(set(merged["sources"]))
        
        result.append(merged)
    
    return result

def print_first_lines(csv_filenames):
    """
    Takes an array of CSV filenames and prints the first line of each file.
    
    Args:
        csv_filenames (list): A list of strings representing CSV filenames
    
    Returns:
        None: This function prints output but does not return anything
    """
    for filename in csv_filenames:
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                first_line = file.readline().strip()
                print(f"First line of {filename}: {first_line}\n")
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found.")
        except Exception as e:
            print(f"Error reading {filename}: {str(e)}")

def parse_markdown_table(file_path):
    """Parse a Markdown table file into attendance data by person"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Skip any lines before the table
    start_idx = 0
    for i, line in enumerate(lines):
        if '|' in line:
            start_idx = i
            break
    
    lines = lines[start_idx:]
    
    # Extract header (people names)
    header = [col.strip() for col in lines[0].split('|') if col.strip()]
    
    # Skip the separator row
    
    # Process each session
    sessions = {}
    for i in range(2, len(lines)):
        line = lines[i].strip()
        if not line or '|' not in line:
            continue
            
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        if not cells:
            continue
            
        session_name = cells[0]
        sessions[session_name] = {}
        
        # For each person, record attendance
        for j in range(1, len(cells)):
            if j < len(header):
                person_name = header[j]
                attendance = cells[j]
                if attendance:  # Only record if not blank
                    sessions[session_name][person_name] = attendance
    
    # Restructure by person
    attendance_by_person = {}
    course_name = os.path.basename(file_path).replace('.md', '')
    
    for person_idx in range(1, len(header)):
        person_name = header[person_idx]
        attendance_by_person[person_name] = {
            "course": course_name,
            "sessions": {}
        }
        
        # Add each session's attendance
        for session_name, session_data in sessions.items():
            if person_name in session_data:
                attendance_by_person[person_name]["sessions"][session_name] = session_data[person_name]
        
        # Calculate summary stats
        total_sessions = len(sessions)
        attended = sum(1 for s in attendance_by_person[person_name]["sessions"].values() 
                      if s in ['A', 'X'])  # A or X counts as attendance
        justified = sum(1 for s in attendance_by_person[person_name]["sessions"].values() 
                       if s == 'J')
        
        attendance_by_person[person_name]["stats"] = {
            "total_sessions": total_sessions,
            "attended": attended,
            "justified": justified,
            "attendance_rate": round(attended / total_sessions * 100, 2) if total_sessions else 0
        }
    
    return attendance_by_person

def normalize_spanish_name(name):
    """Normalize Spanish names by removing accents for comparison purposes"""
    import unicodedata
    
    # Normalize to decomposed form (separate character and diacritic)
    normalized = unicodedata.normalize('NFD', name)
    
    # Remove diacritical marks
    ascii_name = ''.join(c for c in normalized if not unicodedata.combining(c))
    
    # Return lowercased version
    return ascii_name.lower().strip()

def match_person_name(name, people_data):
    """Try to match a name from the attendance table to a person in the JSON data
    using word-level matching to handle naming variations."""
    # Normalize and tokenize the search name
    name_lower = name.lower().strip()
    name_normalized = normalize_spanish_name(name)
    name_words = set(name_normalized.split())
    
    # Remove common Spanish conjunctions and titles
    filtered_words = set()
    common_words = {'de', 'del', 'la', 'las', 'los', 'y', 'e', 'don', 'doña', 'dr', 'dra'}
    for word in name_words:
        if word not in common_words:
            filtered_words.add(word)
    
    name_words = filtered_words if filtered_words else name_words
    
    best_match = None
    best_match_score = 0
    
    # Try to find the best match across all people
    for idx, person in enumerate(people_data):
        person_name = person["nombre"]
        person_normalized = normalize_spanish_name(person_name)
        person_words = set(person_normalized.split())
        
        # Remove common Spanish conjunctions and titles
        person_filtered_words = set()
        for word in person_words:
            if word not in common_words:
                person_filtered_words.add(word)
        
        person_words = person_filtered_words if person_filtered_words else person_words
        
        # First check for exact matches
        if name_lower == person_name.lower().strip() or name_normalized == person_normalized:
            return idx
        
        # Calculate word overlap score (Jaccard similarity)
        intersection = len(name_words.intersection(person_words))
        union = len(name_words.union(person_words))
        
        if union > 0:
            score = intersection / union
            
            # Require at least one word to match
            if intersection > 0 and score > best_match_score:
                best_match_score = score
                best_match = idx
    
    # Set a threshold for acceptable match quality
    # If at least half the words match OR if one word matches when there are only 1-2 words
    if best_match_score >= 0.5 or (best_match_score > 0 and len(name_words) <= 2):
        return best_match
    
    # If no good match, return None
    return None

def update_json_with_attendance(people_data, attendance_data):
    """Update the people JSON data with attendance information"""
    # For each person in the attendance data
    for name, attendance in attendance_data.items():
        # Try to find matching person in people_data
        person_idx = match_person_name(name, people_data)
        
        if person_idx is not None:
            # Add attendance data to person
            if "attendance" not in people_data[person_idx]:
                people_data[person_idx]["attendance"] = []
            
            # Add this course's attendance
            people_data[person_idx]["attendance"].append(attendance)
            
            # Add source to person's sources
            if "source" in attendance and "sources" in people_data[person_idx]:
                if attendance["source"] not in people_data[person_idx]["sources"]:
                    people_data[person_idx]["sources"].append(attendance["source"])
    
    return people_data

def process_attendance_files(people_data, attendance_dir="./sources/attendance"):
    """Process attendance files and add to people data"""
    if not os.path.exists(attendance_dir):
        print(f"Attendance directory {attendance_dir} does not exist.")
        return people_data
    
    # Process each attendance file
    for filename in os.listdir(attendance_dir):
        if filename.endswith('.md'):
            file_path = os.path.join(attendance_dir, filename)
            print(f"Processing attendance file: {file_path}")
            
            # Parse the attendance data
            attendance_data = parse_markdown_table(file_path)
            
            # Update people data with attendance
            people_data = update_json_with_attendance(people_data, attendance_data)
            
            # Add the file path to the sources for each person
            for name, _ in attendance_data.items():
                person_idx = match_person_name(name, people_data)
                if person_idx is not None:
                    if "sources" not in people_data[person_idx]:
                        people_data[person_idx]["sources"] = []
                    if file_path not in people_data[person_idx]["sources"]:
                        people_data[person_idx]["sources"].append(file_path)
    
    return people_data

def main():
    # Process CSV files
    dirname = "./sources/"
    filenames = [
        "2023-1.csv", "2023-2.csv", 
        "2024-1.csv", "2024-2.csv",
        "2024-2-batalla.csv", "2024-2-concordia.csv",
        "general-interest.csv"
    ]
    filenames = [dirname + filename for filename in filenames]
    
    people_data = process_csv_files(filenames)
    
    # Process attendance files
    people_data = process_attendance_files(people_data)
    
    # Save to JSON
    with open("crmdata.json", "w", encoding="utf-8") as f:
        json.dump(people_data, f, ensure_ascii=False, indent=2)
    
    print(f"Processed {len(people_data)} unique contacts and saved to contact_info.json")

if __name__ == "__main__":
    main()

