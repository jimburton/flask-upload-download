from flask import render_template, flash,  url_for, redirect, send_file
from app import app
from app.forms import MenuUploadCSVForm, MenuForm
from uuid import uuid4
from werkzeug.utils import secure_filename
import os
import csv
import io
import ast
import tempfile as tfile
import urllib

# Global var holding the menu, parsed from the csv.
menu_items = {}
# Flag to check whether this is the first request, used to load the menu_items.
first_request = True

@app.before_request
def before_first_request():
    """Hook to run before the first request. Loads the CSV file containing the menu."""
    global first_request
    global menu_items
    if first_request:
        first_request = False
        menu_file = os.path.join(app.config['DATA_FOLDER'], "menu.csv")
        try:
            with open(menu_file) as csv_file:
                reader = csv.reader(csv_file)
                next(reader, None)  # skip the headers
                for item in reader:
                    if item[0] not in menu_items:
                        menu_items[item[0]] = []
                    menu_items[item[0]].append(item[1:])
        except Exception as err:
            app.logger.error(f'Exception occurred: {err=}')

@app.route("/")
def home():
    """View for the home page."""
    return render_template('home.html', name='James', title="Home")

@app.route('/menu')
def menu():
    """View that displays the menu."""
    global menu_items
    return render_template('menu.html', title='Menu', menu=menu_items)

@app.route('/order', methods=['GET', 'POST'])
def order():
    """
    View presenting a form allowing the user to order a meal. On form submission the browser is
    redirected to display the receipt.
    """
    global menu_items
    form = MenuForm(menu_items)
    if form.validate_on_submit():
        starter = lookup_dish('Starter', form.starter.data)
        main    = lookup_dish('Main', form.main.data)
        desert  = lookup_dish('Desert', form.desert.data)
        total   = float(starter[1]) + float(main[1]) + float(desert[1])
        order = {"starter": starter, "main": main, "desert": desert, "total": total}
        return redirect(url_for('receipt', order=order))
    return render_template('order.html', title='Order', form=form)

@app.route('/receipt/<order>')
def receipt(order):
    """View that displays the receipt for an order."""
    order_dict = ast.literal_eval(order)
    return render_template('receipt.html', title='Receipt', order=order_dict)

@app.route('/download_receipt/<order>')
def download_receipt(order):
    """View that creates a receipt file then sends it to the client as an attachment."""
    order_dict = ast.literal_eval(order)
    try:
        fmt_line = '{0:<10} {1:<25} {2:>8}' # format the file contents in columns.
        sep_line = '-'*45
        starter_line = fmt_line.format('Starter', order_dict["starter"][0], order_dict["starter"][1])
        main_line = fmt_line.format('Main', order_dict["main"][0], order_dict["main"][1])
        desert_line = fmt_line.format('Desert', order_dict["desert"][0], order_dict["desert"][1])
        total_line = '{0:>36} {1:>8}'.format('Total:', fmt_float(order_dict["total"]))
        text = f'Receipt\n\n{sep_line}\n{starter_line}\n{main_line}\n{desert_line}\n{sep_line}\n{total_line}\n'
        mem = io.BytesIO()
        mem.write(text.encode(encoding="utf-8"))
        mem.seek(0)
        return send_file(mem, as_attachment=True, download_name='receipt.txt', mimetype='text/plain')
    except Exception as err:
        flash('File Download failed. Please try again', 'danger')
        app.logger.error(f'Exception occurred in File Download: {err=}')
    return redirect(url_for('receipt', order=order_dict))

@app.route('/upload_menu', methods=['GET', 'POST'])
def upload_menu():
    """
    View that allows the user to upload a CSV file containing a menu, then sorts the data by course and
    price and writes the new CSV to a temp file. Finally it reloads the page with an embedded script
    that will load the route '/download_menu' in the background.
    """
    menu = {}
    form = MenuUploadCSVForm()
    if form.validate_on_submit():
        if form.file.data:
            # Make a unique name for the file and save it to the uploads directory.
            unique_str = str(uuid4())
            filename = secure_filename(f'{unique_str}-{form.file.data.filename}')
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            form.file.data.save(filepath)
            try:
                # Open the file and parse its contents into a dict.
                with open(filepath, newline='') as csvFile:
                    reader = csv.reader(csvFile)
                    error_count = 0
                    header_row = next(reader)
                    if header_row != ['Course', 'Dish', 'Price']:
                        form.file.errors.append(
                            'First row of file must be a Header row containing "Course,Dish,Price"')
                        raise ValueError()
                    for idx, row in enumerate(reader):
                        course = row[0]
                        dish = row[1]
                        price = row[2]
                        row_num = idx + 2  # Spreadsheets have the first row as 0, and we skip the header
                        if error_count > 10:
                            form.file.errors.append('Too many errors found, any further errors omitted')
                            raise ValueError()
                        if len(row) != 3:
                            form.file.errors.append(f'Row {row_num} does not have precisely 3 fields')
                            error_count += 1
                            continue
                        if not is_float(price):
                            form.file.errors.append(f'Row {row_num} has an invalid price: "{price}"')
                            error_count += 1
                        if error_count == 0:
                            if course not in menu:
                                menu[course] = []
                        menu[course].append((dish,float(price)))
                if error_count > 0:
                    raise ValueError
                flash('Menu uploaded', 'success')
            except Exception as err:
                flash('File upload failed.'
                      ' Please correct your file and try again', 'danger')
                app.logger.error(f'Exception occurred: {err=}')
            finally:
                silent_remove(filepath)
            try:
                # Sort the uploaded data then write it to a CSV. 
                app.logger.debug(f'{sorted(menu.keys())=}')
                output_str = ""
                line = ['Course','Dish','Price']
                output_str += ','.join(line) + '\n'
                for key in sorted(menu.keys()):
                    app.logger.debug(f'{menu[key]=}')
                    course_items = menu[key]
                    course_items.sort(key=lambda item: float(item[1]))
                    app.logger.debug(f'{course_items=}')
                    for item in course_items:
                        line = [key]
                        line.append(item[0])
                        line.append(fmt_float(item[1]))
                        output_str += ','.join(line) + '\n'
                
                fd, path = tfile.mkstemp(suffix=".csv",prefix="menu")
                with os.fdopen(fd, "w+") as fo:
                    fo.write(output_str)
                app.logger.debug(f'{path=}')
                flash('Your download will begin shortly', 'success')
                esc_path = urllib.parse.quote(path, safe='')
                return render_template('upload_menu.html', title='Upload Menu File', form=form, download_file=esc_path)
            except Exception as err:
                flash('File download failed.', 'danger')
                app.logger.error(f'Exception occurred: {err=}')
            
    return render_template('upload_menu.html', title='Upload Menu File', form=form, download_file=None)

@app.route('/download_menu/<path>')
def download_menu(path):
    """Read the file at 'path', delete it then send the contents to the client."""
    unesc_path = urllib.parse.unquote(path)
    app.logger.debug(f'{unesc_path=}')
    try:
        with open(unesc_path, 'r') as f:
            contents = f.read()
        os.remove(unesc_path)
        mem = io.BytesIO()
        mem.write(contents.encode(encoding="utf-8"))
        mem.seek(0)
        return send_file(mem, as_attachment=True, download_name='menu.csv', mimetype='text/csv')
    except Exception as err:
        app.logger.error(f'Exception occurred: {err=}')
    finally:
        silent_remove(path)

#############################
# Helper functions
#############################

def is_float(num: str) -> bool:
    """Returns True if num can be converted to a float, otherwise false."""
    try:
        float(num)
        return True
    except ValueError:
        return False

def fmt_float(f: float) -> str:
    """Format a float as a string with two decimal places."""
    return "{:.2f}".format(f)

def lookup_dish(course: str, dish: str) -> tuple[str,str]|None:
    """Look up a dish in the global menu_items dict. Returns a tuple (dish,price) or None."""
    global menu_items
    app.logger.debug(f'Looking up {course}, {dish}')
    app.logger.debug(f'Search in {menu_items[course]}')
    if dish is None:
        return ('No selection','0.0')
    for data in menu_items[course]:
        if data[0] == dish:
            return (data[0],data[1])
    return None

def silent_remove(filepath: str) -> None:
    """Utility function to attempt to remove a file but silently cancel any exceptions if anything goes wrong."""
    try:
        os.remove(filepath)
    except Exception:
        pass
    return
