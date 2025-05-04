import re

def format_message(text):
    """
    Format message with simple HTML tags.
    This is used to format plain text to HTML.
    """
    # Convert markdown-style bold
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Convert markdown-style italic
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Convert markdown-style code
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # Convert line breaks
    text = text.replace('\n', '<br>')
    
    return text
