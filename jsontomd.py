import json
import os
import re

def sanitize_filename(name):
    """Convert name to a valid filename"""
    # Replace invalid filename characters with underscores
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def normalize_spanish_name(name):
    """Normalize Spanish names by removing accents for comparison and output purposes"""
    import unicodedata
    
    # Normalize to decomposed form (separate character and diacritic)
    normalized = unicodedata.normalize('NFD', name)
    
    # Remove diacritical marks
    ascii_name = ''.join(c for c in normalized if not unicodedata.combining(c))
    
    return ascii_name

def analyze_person_data(person):
    """Analyze text content in person data for tags and metadata"""
    # Results dictionary
    results = {
        "tags": [],
        "courses": []
    }
    
    # Concatenate all text fields to search for patterns
    text_content = ""
    
    # Add basic fields
    for field in ["nombre", "carrera", "generacion"]:
        if field in person and person[field]:
            text_content += " " + str(person[field])
    
    # Add text from postulaciones
    if "postulaciones" in person and person["postulaciones"]:
        for postulacion in person["postulaciones"]:
            for key, value in postulacion.items():
                if isinstance(value, str):
                    text_content += " " + value
    
    # Convert to lowercase for case-insensitive matching
    text_content = text_content.lower()
    
    # Detect MSc tag
    if any(term in text_content for term in ["magister", "msc", "máster", "master", "magíster"]):
        results["tags"].append("#msc")
        
    # Detect PhD tag
    if any(term in text_content for term in ["phd", "ph.d", "ph.d.", "doctorado", "doctorate", "doctoral"]):
        results["tags"].append("#phd")
    
    # Detect IIC course numbers
    iic_matches = re.findall(r'iic\d+', text_content)
    # Remove duplicates and convert to uppercase
    unique_courses = list(set([match.upper() for match in iic_matches]))
    results["courses"] = unique_courses
    
    return results

def generate_markdown(person, output_dir):
    """Generate a Markdown file for a person"""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Normalize name for consistency in both display and filename
    person_nombre = person["nombre"]
    person_nombre_normalized = normalize_spanish_name(person_nombre)
    
    # Sanitize name for filename
    filename = sanitize_filename(person_nombre_normalized)
    if not filename.strip():
        # Use email or a placeholder if name is empty
        if person.get("correo"):
            filename = sanitize_filename(person["correo"].split("@")[0])
        else:
            filename = f"person_{hash(json.dumps(person, sort_keys=True))}"
    
    filepath = os.path.join(output_dir, f"{filename}.md")
    
    # Analyze person data for tags and metadata
    analysis = analyze_person_data(person)
    
    # Calculate total attendance stats across all courses
    total_attended_sessions = 0
    total_sessions = 0
    if "attendance" in person and person["attendance"]:
        for course_attendance in person["attendance"]:
            total_attended_sessions += course_attendance["stats"]["attended"]
            total_sessions += course_attendance["stats"]["total_sessions"]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        # Write YAML frontmatter
        f.write("---\n")
        f.write(f"nombre: \"{person_nombre}\"\n")
        f.write(f"nombre_normalized: \"{person_nombre_normalized}\"\n")
        f.write(f"correo: \"{person['correo']}\"\n")
        f.write(f"telegram: \"{person['telegram']}\"\n")
        f.write(f"carrera: \"{person['carrera']}\"\n")
        f.write(f"generacion: \"{person['generacion']}\"\n")
        
        # Add total attendance stats
        f.write(f"total_attended_sessions: {total_attended_sessions}\n")
        f.write(f"total_sessions: {total_sessions}\n")
        
        # Add forms from postulaciones
        if "postulaciones" in person and person["postulaciones"]:
            f.write("forms:\n")
            for postulacion in person["postulaciones"]:
                if "form" in postulacion:
                    # Remove .csv extension from form name
                    form_name = postulacion['form']
                    if form_name.endswith('.csv'):
                        form_name = form_name[:-4]
                    f.write(f"  - \"{form_name}\"\n")
        
        # Add sources if available
        if "sources" in person:
            f.write("sources:\n")
            for source in person["sources"]:
                f.write(f"  - \"{source}\"\n")
        
        # Add courses as frontmatter data
        if analysis["courses"]:
            f.write("courses:\n")
            for course in analysis["courses"]:
                f.write(f"  - \"{course}\"\n")
        
        # Add attendance data if available
        if "attendance" in person and person["attendance"]:
            f.write("attendance:\n")
            for course_attendance in person["attendance"]:
                course_name = course_attendance["course"]
                f.write(f"  {course_name}:\n")
                
                # Add summary stats directly in frontmatter
                f.write(f"    total_sessions: {course_attendance['stats']['total_sessions']}\n")
                f.write(f"    attended: {course_attendance['stats']['attended']}\n")
                f.write(f"    justified: {course_attendance['stats']['justified']}\n")
                f.write(f"    attendance_rate: {course_attendance['stats']['attendance_rate']}\n")
                
                # Add detailed session attendance directly in frontmatter
                f.write(f"    sessions:\n")
                for session, status in course_attendance["sessions"].items():
                    f.write(f"      {session}: {status}\n")
        
        f.write("---\n\n")
        
        # Write contact information as a bulleted list
        f.write("## Contact Information\n\n")
        f.write(f"* **Name**: {person['nombre']}\n")
        f.write(f"* **Email**: {person['correo']}\n")
        f.write(f"* **Telegram**: {person['telegram']}\n")
        f.write(f"* **Degree/Program**: {person['carrera']}\n")
        f.write(f"* **Generation**: {person['generacion']}\n")
        f.write("\n")
        
        # Add attendance summary if available
        if "attendance" in person and person["attendance"]:
            f.write("## Attendance\n\n")
            
            for course in person["attendance"]:
                f.write(f"### {course['course']}\n\n")
                f.write(f"* **Total Sessions**: {course['stats']['total_sessions']}\n")
                f.write(f"* **Sessions Attended**: {course['stats']['attended']}\n")
                f.write(f"* **Justified Absences**: {course['stats']['justified']}\n")
                f.write(f"* **Attendance Rate**: {course['stats']['attendance_rate']}%\n")
                
                # Add detailed attendance table
                f.write("\n| Session | Status |\n")
                f.write("|---------|--------|\n")
                for session, status in course["sessions"].items():
                    f.write(f"| {session} | {status} |\n")
                f.write("\n")
        
        # Write essay answers as paragraphs
        if "postulaciones" in person and person["postulaciones"]:
            f.write("## Application Responses\n\n")
            
            for postulacion in person["postulaciones"]:
                form_name = postulacion.get("form", "Unknown Form")
                f.write(f"### Form: {form_name}\n\n")
                
                for key, value in postulacion.items():
                    # Skip the form name field
                    if key == "form":
                        continue
                    
                    # Format the question key to be more readable
                    question = key.replace("_", " ").capitalize()
                    
                    # Write the question and answer as a paragraph
                    f.write(f"**{question}**\n\n{value}\n\n")

        # Get all tags
        tags = []

        # Add postulaciones tags
        if "postulaciones" in person and person["postulaciones"]:
            for postulacion in person["postulaciones"]:
                if "form" in postulacion:
                    # Remove .csv extension from form name
                    form_name = postulacion['form']
                    if form_name.endswith('.csv'):
                        form_name = form_name[:-4]
                    tags.append(f"#postulaciones/{form_name}")
        
        # Add attendance tags
        if "attendance" in person and person["attendance"]:
            for course in person["attendance"]:
                course_name = course["course"]
                tags.append(f"#attendance/{course_name}")
                
                # Tag high attendance only
                if course["stats"]["attendance_rate"] >= 50:
                    tags.append(f"#high-attendance")
        
        if analysis["tags"]:
            tags.extend(analysis["tags"])
        
        # Write all tags at the end of the file
        if tags:
            f.write("\n")
            f.write(" ".join(tags))

def main():
    # Open the JSON file
    try:
        with open("crmdata.json", 'r', encoding='utf-8') as f:
            people_data = json.load(f)
    except Exception as e:
        print(f"Error reading crmdata.json: {str(e)}")
        return
    
    # Create Markdown files
    output_dir = "./md"
    for person in people_data:
        generate_markdown(person, output_dir)
    
    print(f"Created {len(people_data)} Markdown files in {output_dir}/")

if __name__ == "__main__":
    main()
