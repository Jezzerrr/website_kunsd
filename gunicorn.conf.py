# Instellingen voor gunicorn (de webserver op Render). Gunicorn leest dit bestand vanzelf.

# Hoe lang een bewerking mag duren voordat gunicorn hem afbreekt (standaard 30 seconden).
# Op het Render free plan is de processor traag: een grote foto (bijv. bij Paint By Number)
# kan dan langer dan 30 seconden duren. Gunicorn stopt de bewerking dan halverwege en de bezoeker krijgt een
# HTML-foutpagina in plaats van een plaatje.
timeout = 180
