from jinja2 import Environment, FileSystemLoader
import os
from datetime import datetime

def generate_portfolio_html(data, output_path='portfolio.html', template_name='portfolio_template/index.html'):
    try:
        # Setup Jinja2 Environment
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template(template_name)
        
        # Add current date to data
        data['now'] = datetime.now().strftime('%B %d, %Y')
        
        # Ensure education is a list of dicts
        if not isinstance(data.get('education', None), list) or not all(isinstance(e, dict) for e in data['education']):
            data['education'] = []
        
        # Ensure projects are properly formatted
        if not isinstance(data.get('projects', None), list):
            data['projects'] = []
        
        # Render the HTML using resume data
        html = template.render(data=data)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write the rendered HTML to a file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return f"✅ Portfolio generated at: {output_path}"
    
    except Exception as e:
        return f"❌ Error generating HTML: {str(e)}"