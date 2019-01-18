import secrets
import os
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from flaskcalendar import app, db, bcrypt
from flaskcalendar.forms import RegistrationForm, LoginForm, AddProfessorForm, AddStudentForm, AddSubjectForm, UpdateAccountForm
from flaskcalendar.models import User,Professor, Student, Subject, ProfessorSubjects, Event, History
from flask_login import login_user, current_user, logout_user, login_required
from datetime import datetime, timedelta
import itertools

# TODO: Move this to helpers?
def addToHistory(instance,action):
    hist = History(time = datetime.utcnow(), entry=(instance), action=action)
    db.session.add(hist)
    db.session.commit()


def save_pictures(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = str(current_user.id) + '_' + random_hex + f_ext
    picture_path = os.path.join(app.root_path,'static\pics', picture_fn)

    output_size = (125,125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route("/")
@app.route("/home")
def home():
    # Get dates already in order
    events = Event.query.order_by("time")
    dates = []
    time_delta = timedelta(hours=3)
    for a, b in itertools.combinations(events, 2):
        if (a.student == b.student or a.professor == b.professor) and (-time_delta < a.time - b.time  < time_delta):
            flash(f"event {a.id} and {b.id} ",'danger')
        if a.time.date() not in dates:
            dates.append(a.time.date())
        if b.time.date() not in dates:
            dates.append(b.time.date())

    return render_template('home.html', events= events, dates=dates)

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/register", methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Account created for {form.username.data}!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password,form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful!', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/history", methods=['GET','POST'])
@login_required
def history():
    # Get events in desc order, first most recent
    events = History.query.order_by("id desc")
    return render_template('history.html', events=events)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/account", methods=['GET','POST'])
@login_required
def account():
    form = UpdateAccountForm()
    image_file = url_for('static', filename='pics/' + current_user.image_file)
    # Update user
    if form.validate_on_submit():
        # Check if user uploaded a picture
        if form.picture.data:
            # TODO: Delete old picture
            picture_file = save_pictures(form.picture.data)
            current_user.image_file = picture_file
        # Update user info
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated','success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        # Fill form with current info
        form.username.data = current_user.username
        form.email.data = current_user.email
    return render_template('account.html', title='Account', image_file=image_file, form=form)

@app.route("/add", methods=['GET','POST'])
@login_required
def add():
    return render_template('add.html', title='Add')


@app.route("/add_professor", methods=['GET','POST'])
def add_professor():
    form = AddProfessorForm()
    sList = Subject.query.filter_by()
    if form.validate_on_submit():
        instance = Professor(name=form.name.data, last_name=form.last_name.data, email=form.email.data, phone=form.phone.data)
        db.session.add(instance)
        # Have to add before commit, otherwise db get corrupted
        addToHistory(instance,'add')
        db.session.commit()
        # Link professor to Subject if any selected
        if request.form.get("Subject"):
            for subject_id in request.form.getlist("Subject"):
                subject_id = int(subject_id)
                db.session.add(ProfessorSubjects(professor_id=instance.id,subject_id=subject_id))
                db.session.commit()
        flash(f'{instance.name} {instance.last_name} added as a {instance.__class__.__name__}!', 'success')
        return redirect(url_for('professors'))
    return render_template('add_professor.html',form=form, subjectsList=sList)

@app.route("/add_student", methods=['GET','POST'])
def add_student():
    form = AddStudentForm()
    if form.validate_on_submit():
        instance = Student(name=form.name.data, last_name=form.last_name.data, email=form.email.data, phone=form.phone.data)
        db.session.add(instance)
        addToHistory(instance,'add')
        db.session.commit()
        flash(f'{instance.name} {instance.last_name} added as a {instance.__class__.__name__}!', 'success')
        return redirect(url_for('students'))
    return render_template('add_student.html',form=form)

@app.route("/add_subject", methods=['GET','POST'])
def add_subject():
    form = AddSubjectForm()
    if form.validate_on_submit():
        instance = Subject(subject=form.subject.data)
        db.session.add(instance)
        addToHistory(instance,'add')
        db.session.commit()
        flash(f'{form.subject.data} added!', 'success')
        return redirect(url_for('subjects'))
    return render_template('add_subject.html', form=form)

@app.route("/link", methods=['GET','POST'])
def link():
    professorsList = Professor.query
    subjectsList = Subject.query
    if request.form.getlist("Subject") and request.form.get("Professor"):
        # If multiple subjects selected
        for subject_id in request.form.getlist("Subject"):
            subject_id = int(subject_id)
            professor_id = int(request.form.get("Professor"))
            # Check if realationship doen's exist already
            if ProfessorSubjects.query.filter_by(professor_id=professor_id, subject_id=subject_id).first():
                flash(f'{professorsList.filter_by(id=professor_id).first().fullName()} already linked to {subjectsList.filter_by(id=subject_id).first().subject}!', 'danger')
            else:
                instance = ProfessorSubjects(professor_id=professor_id, subject_id=subject_id)
                db.session.add(instance)
                db.session.commit()
                flash(f'{professorsList.filter_by(id=professor_id).first().fullName()} linked to {subjectsList.filter_by(id=subject_id).first().subject}!', 'success')
    return render_template('link.html', professorsList=professorsList, subjectsList=subjectsList)

@app.route("/edit", methods=['GET','POST'])
def edit():
    professorsList, subjectsList, studentsList = Professor.query, Subject.query, Student.query
    if request.args.get('Professor'):
        return redirect(url_for('edit_professor', Professor=request.args.get('Professor')))
    elif request.args.get('Subject'):
        return redirect(url_for('edit_subject', Subject=request.args.get('Subject')))
    elif request.args.get('Student'):
        return redirect(url_for('edit_student', Student=request.args.get('Student')))

    return render_template('edit.html', professorsList=professorsList, subjectsList=subjectsList, studentsList=studentsList)

@app.route("/edit_professor", methods=['GET','POST'])
def edit_professor():
    form = AddProfessorForm()

    if form.validate_on_submit():
        professor_id = int(request.form.get("instance_id"))
        instance = Professor.query.filter_by(id=professor_id).first()
        instance.name = form.name.data
        instance.last_name  = form.last_name.data
        instance.email  = form.email.data
        instance.phone = form.phone.data
        addToHistory(instance,'edit')
        db.session.commit()
        flash(f"{instance.name} {instance.last_name}' account has been updated",'success')
        # POST/ GET redirect better to use redirect instead update
        # TODO: Redirect to previous page
        return redirect(url_for('edit'))
    elif request.method == 'GET' and request.args.get('Professor'):
        professor_id = int(request.args.get('Professor'))
        instance = Professor.query.filter_by(id=professor_id).first()
        form.name.data = instance.name
        form.last_name.data = instance.last_name
        form.email.data = instance.email
        form.phone.data = instance.phone
        return render_template('edit_professor.html', form=form, instance=instance)
    elif request.args.to_dict() == {}:
        # TODO: Simple list of professors ready to edit
        professorsList = Professor.query
        return render_template('edit_professor.html', pList = professorsList)
    else:
        flash(f"Something went wrong",'danger')
    return redirect(url_for('edit'))

@app.route("/edit_student", methods=['GET','POST'])
def edit_student():
    form = AddStudentForm()

    # If method POST
    if form.validate_on_submit():
        student_id = int(request.form.get("instance_id"))
        instance = Student.query.filter_by(id=student_id).first()
        instance.name = form.name.data
        instance.last_name  = form.last_name.data
        instance.email  = form.email.data
        instance.phone = form.phone.data
        addToHistory(instance,'edit')
        db.session.commit()
        flash(f"{instance.name} {instance.last_name}' account has been updated",'success')
        # POST/ GET redirect better to use redirect instead update
        # TODO: Redirect to previous page
        return redirect(url_for('edit'))
    # If access via /edit
    elif request.method == 'GET' and request.args.get('Student'):
        student_id = int(request.args.get('Student'))
        instance = Student.query.filter_by(id=student_id).first()
        form.name.data = instance.name
        form.last_name.data = instance.last_name
        form.email.data = instance.email
        form.phone.data = instance.phone
        return render_template('edit_student.html', form=form, instance=instance)
    elif request.args.to_dict() == {}:
        studentsList = Student.query
        return render_template('edit_student.html', sList = studentsList)
    else:
        flash(f"Something went wrong",'danger')
    return redirect(url_for('edit'))

@app.route("/edit_subject", methods=['GET','POST'])
def edit_subject():
    form = AddSubjectForm()

    # If method is POST
    if form.validate_on_submit():
        subject_id = int(request.form.get("instance_id"))
        instance = Subject.query.filter_by(id=subject_id).first()
        instance.subject = form.subject.data
        addToHistory(instance,'edit')
        db.session.commit()
        flash(f"{instance.subject}' has been updated",'success')
        # POST/ GET redirect better to use redirect instead update
        # TODO: Redirect to previous page
        return redirect(url_for('edit'))
    # If access via /edit
    elif request.method == 'GET' and request.args.get('Subject'):
        subject_id = int(request.args.get('Subject'))
        instance = Subject.query.filter_by(id=subject_id).first()
        form.subject.data = instance.subject
        return render_template('edit_subject.html', form=form, instance=instance)
    elif request.args.to_dict() == {}:
        subjectsList = Subject.query
        return render_template('edit_subject.html', sjList = subjectsList)
    else:
        flash(f"Something went wrong",'danger')
    return redirect(url_for('edit'))

@app.route("/events/create", methods=['GET','POST'])
@login_required
def create_event():
    professorsList = Professor.query
    subjectsList = Subject.query
    studentsList = Student.query
    # TODO: What to do with this, maybe add ajax
    ProfessorSubjectsList = ProfessorSubjects.query
    today = datetime.now().strftime("%Y-%m-%dT%H:%M")

    if request.method == 'POST':
        professor_id = request.form.get('Professor')
        student_id = request.form.get('Student')
        subject_id = request.form.get('Subject')
        time = request.form.get('Time')
        author_id = int(current_user.id)
        # TODO: Daytime saving?
        time_dt = datetime.strptime(time,"%Y-%m-%dT%H:%M")
        instance = Event(professor_id=professor_id, student_id=student_id, subject_id=subject_id, author_id=author_id, time=time_dt)
        db.session.add(instance)
        addToHistory(instance,'add')
        db.session.commit()

        professor_obj = professorsList.filter_by(id=professor_id).first()
        student_obj = studentsList.filter_by(id=student_id).first()
        subject_obj = subjectsList.filter_by(id=subject_id).first()

        flash(f"Event created for {professor_obj.fullName()} with {student_obj.fullName()} of {subject_obj.subject} at {instance.time}",'success')
        return redirect(url_for('create_event'))
    return render_template('create_event.html',today=today, title='Create Event',professorsList=professorsList, subjectsList=subjectsList, studentsList=studentsList, ProfessorSubjectsList = ProfessorSubjectsList)


@app.route("/events")
def events():
    eventsList = Event.query.order_by("id desc")
    return render_template('events.html',title='Events', eList = eventsList)


@app.route("/professor")
def professor():
    if request.method == 'GET' and request.args.get('id'):
        professor_id = int(request.args.get('id'))
        instance = Professor.query.filter_by(id=professor_id).first()

        return render_template('professor.html',title=f'{instance.fullName()} Events', instance=instance)
    return redirect(url_for('professors'))

@app.route("/subject")
def subject():
    if request.method == 'GET' and request.args.get('id'):
        subject_id = int(request.args.get('id'))
        instance = Subject.query.filter_by(id=subject_id).first()
        return render_template('subject.html',title=f'{instance.subject} Events',instance=instance)
    return redirect(url_for('subjects'))

@app.route("/student")
def student():
    if request.method == 'GET' and request.args.get('id'):
        student_id = int(request.args.get('id'))
        instance = Student.query.filter_by(id=student_id).first()
        return render_template('student.html',title=f'{instance.fullName()} Events',instance=instance)
    return redirect(url_for('students'))



@app.route("/professors")
def professors():
    professorsList = Professor.query
    return render_template('professors.html', pList = professorsList)

@app.route("/subjects")
def subjects():
    subjectsList = Subject.query
    return render_template('subjects.html', sjList = subjectsList)


@app.route("/students")
def students():
    studentsList = Student.query
    return render_template('students.html', sList = studentsList)

# TODO: Delete things
# TODO: Search page with parameters
# TODO: Create events only with subjects of professor

@app.route("/event")
def event():
    return redirect(url_for("events"))

@app.route("/event/<int:event_id>")
def event_id(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event.html', event = event)

@app.route("/event/<int:event_id>/edit", methods=['GET','POST'])
@login_required
def event_update(event_id):
    instance = Event.query.get_or_404(event_id)
    if instance.author != current_user:
        abort(403)

    professorsList = Professor.query
    subjectsList = Subject.query
    studentsList = Student.query

    if request.method == 'POST' and request.values:
        instance.professor_id = int(request.form.get('Professor'))
        instance.student_id = int(request.form.get('Student'))
        instance.subject_id = int(request.form.get('Subject'))
        time = request.form.get('Time')
        time_dt = datetime.strptime(time,"%Y-%m-%dT%H:%M")
        instance.time = time_dt
        addToHistory(instance,'edit')
        db.session.commit()
        flash(f"Event {instance.id} has been updated correctly",'success')
        return redirect(url_for('event_id', event_id=instance.id))

    return render_template('edit_event.html', title='Edit Event',professorsList=professorsList, subjectsList=subjectsList, studentsList=studentsList, event=instance)

@app.route("/event/<int:event_id>/delete", methods=['POST'])
@login_required
def event_delete(event_id):
    instance = Event.query.get_or_404(event_id)
    if instance.author != current_user:
        abort(403)
    addToHistory(instance,'delete')
    db.session.delete(instance)
    db.session.commit()
    flash(f"Event has been deleted correctly",'success')
    return redirect(url_for('events'))


