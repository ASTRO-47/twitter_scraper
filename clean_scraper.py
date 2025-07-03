import re

# Read the current scraper file
with open('app/scraper.py', 'r') as f:
    content = f.read()

# Remove all print statements
cleaned_content = re.sub(r'\s*print\([^)]*\)\s*\n', '', content)

# Write the cleaned version
with open('app/scraper.py', 'w') as f:
    f.write(cleaned_content)

print("Cleaned all print statements from scraper.py")
