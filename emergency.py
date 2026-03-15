EMERGENCY_KEYWORDS = [

"chest pain",
"cannot breathe",
"difficulty breathing",
"severe bleeding",
"fainted",
"unconscious"

]

def check_emergency(text):

    for word in EMERGENCY_KEYWORDS:

        if word in text.lower():

            return True

    return False