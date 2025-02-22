from flask_wtf import FlaskForm
from flask_wtf.file import FileRequired, FileAllowed
from wtforms import FileField, SubmitField, RadioField


class MenuUploadCSVForm(FlaskForm):
    file = FileField('Upload a CSV File', validators=[FileRequired(), FileAllowed(['csv'])])
    submit = SubmitField('Upload')

class MenuForm(FlaskForm):
    starter = RadioField('Starter',render_kw={'class':'list-unstyled'}, validate_choice=False)
    main    = RadioField('Main',render_kw={'class':'list-unstyled'}, validate_choice=False)
    desert  = RadioField('Desert',render_kw={'class':'list-unstyled'}, validate_choice=False)
    submit  = SubmitField('Order')

    def __init__(self, menu_items, *args, **kwargs):
        super(MenuForm, self).__init__(*args, **kwargs)
        starter_choices = [(name,f'{name} ({price})') for [name,price] in menu_items['Starter']]
        main_choices    = [(name,f'{name} ({price})') for [name,price] in menu_items['Main']]
        desert_choices  = [(name,f'{name} ({price})') for [name,price] in menu_items['Desert']]
        self.starter.choices = starter_choices
        self.main.choices    = main_choices
        self.desert.choices  = desert_choices
        
