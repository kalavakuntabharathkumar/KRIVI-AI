# html_generator.py

from jinja2 import Environment, FileSystemLoader
import os

def generate_portfolio_html(data, output_path='generated_portfolio.html', template_name='template_01/index.html'):
    try:
        # Setup Jinja2 Environment
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template(template_name)

        # Render the HTML using resume data
        html = template.render(data=data)

        # Write the rendered HTML to a file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"✅ Portfolio generated at: {output_path}")

    except Exception as e:
        print(f"❌ Error generating HTML: {e}")
