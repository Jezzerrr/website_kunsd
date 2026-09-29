def make_contact_email(subject, sender_email, message):

    return f"""
====================================
KUNSD WEBSITE CONTACTFORMULIER
====================================

Afzender:
{sender_email}

Onderwerp:
{subject}

------------------------------------

{message}
"""
