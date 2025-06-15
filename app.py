from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from datetime import date, datetime
import re
from fpdf import FPDF
import io

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

def get_db_connection():
    conn = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="panda",
        database="fitness"
    )
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Email validation: must contain '@'
        if '@' not in email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email address!')
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute("SELECT * FROM Users WHERE Email = %s", (email,))
        if cursor.fetchone():
            flash('Email already registered or invalid entry!')
            cursor.close()
            conn.close()
            return render_template('register.html')

        # Generate unique UserID
        cursor.execute("SELECT MAX(UserID) FROM Users")
        result = cursor.fetchone()
        new_id = 1 if result[0] is None else result[0] + 1

        # Insert new user
        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO Users (UserID, Name, Email, PasswordHash) VALUES (%s, %s, %s, %s)",
            (new_id, name, email, hashed_password)
        )
        conn.commit()

        flash('Registration successful! Please login.')
        cursor.close()
        conn.close()
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE Email = %s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['PasswordHash'], password):
            session['user_id'] = user['UserID']
            session['user_name'] = user['Name']
            cursor.close()
            conn.close()
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password')

        cursor.close()
        conn.close()

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/fitnessgoal', methods=['GET', 'POST'])
def fitnessgoal():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        target_calories = request.form['target_calories']
        target_body_fat = request.form['target_body_fat']
        goal_type = request.form['goal_type']

        # Check if user already has a goal
        cursor.execute("SELECT * FROM FitnessGoal WHERE UserID = %s", (session['user_id'],))
        existing_goal = cursor.fetchone()

        if existing_goal:
            # Update existing goal
            cursor.execute("""
                UPDATE FitnessGoal
                SET TargetCalories = %s, TargetBodyFat = %s, GoalType = %s
                WHERE UserID = %s
            """, (target_calories, target_body_fat, goal_type, session['user_id']))
        else:
            # Get next GoalID
            cursor.execute("SELECT MAX(GoalID) FROM FitnessGoal")
            result = cursor.fetchone()
            new_goal_id = 101 if result['MAX(GoalID)'] is None else result['MAX(GoalID)'] + 1

            # Create new goal
            cursor.execute("""
                INSERT INTO FitnessGoal (GoalID, UserID, TargetCalories, TargetBodyFat, GoalType)
                VALUES (%s, %s, %s, %s, %s)
            """, (new_goal_id, session['user_id'], target_calories, target_body_fat, goal_type))

        conn.commit()
        flash('Fitness goal saved successfully!')
        cursor.close()
        conn.close()
        return redirect(url_for('home'))

    # Get user's current goals
    cursor.execute("SELECT * FROM FitnessGoal WHERE UserID = %s", (session['user_id'],))
    goals = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('fitnessgoal.html', goals=goals)

@app.route('/workoutprogram', methods=['GET', 'POST'])
def workoutprogram():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch the user's goal
    cursor.execute("SELECT GoalID FROM FitnessGoal WHERE UserID = %s", (session['user_id'],))
    goal = cursor.fetchone()

    if not goal:
        flash('Please set a fitness goal first!')
        cursor.close()
        conn.close()
        return redirect(url_for('fitnessgoal'))

    goal_id = goal['GoalID']

    if request.method == 'POST':
        reps = request.form['reps']
        weight_used = request.form['weight_used']
        calorie_burnt = request.form['calorie_burnt']
        duration = request.form['duration']
        log_date = request.form.get('log_date', date.today().isoformat())

        # Get next ProgramID
        cursor.execute("SELECT MAX(ProgramID) FROM WorkoutProgram")
        result = cursor.fetchone()
        new_program_id = 201 if result['MAX(ProgramID)'] is None else result['MAX(ProgramID)'] + 1

        # Insert workout program
        cursor.execute("""
            INSERT INTO WorkoutProgram 
            (ProgramID, UserID, GoalID, Reps, WeightUsed, CalorieBurnt, Duration, LogDate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (new_program_id, session['user_id'], goal_id, reps, weight_used, calorie_burnt, duration, log_date))

        conn.commit()
        flash('Workout program saved successfully!')
        cursor.close()
        conn.close()
        return redirect(url_for('home'))

    # Get user's workout history
    cursor.execute("""
        SELECT * FROM WorkoutProgram 
        WHERE UserID = %s 
        ORDER BY LogDate DESC
    """, (session['user_id'],))
    workouts = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('workoutprogram.html', workouts=workouts, date=date)

@app.route('/bodymeasurement', methods=['GET', 'POST'])
def bodymeasurement():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch the user's goal
    cursor.execute("SELECT * FROM FitnessGoal WHERE UserID = %s", (session['user_id'],))
    goal = cursor.fetchone()

    if not goal:
        flash('Please set a fitness goal first!')
        cursor.close()
        conn.close()
        return redirect(url_for('fitnessgoal'))

    if request.method == 'POST':
        weight = request.form['weight']
        height = request.form['height']
        body_fat = request.form['body_fat']
        chest = request.form['chest']
        hip = request.form['hip']
        log_date = request.form.get('log_date', date.today().isoformat())

        # Get next MeasurementID
        cursor.execute("SELECT MAX(MeasurementID) FROM BodyMeasurement")
        result = cursor.fetchone()
        new_measurement_id = 301 if result['MAX(MeasurementID)'] is None else result['MAX(MeasurementID)'] + 1

        # Insert body measurement
        cursor.execute("""
            INSERT INTO BodyMeasurement 
            (MeasurementID, UserID, GoalID, LogDate, Weight, Height, BodyFatPercentage, Chest, Hip)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (new_measurement_id, session['user_id'], goal['GoalID'], log_date, weight, height, body_fat, chest, hip))

        conn.commit()
        flash('Body measurements saved successfully!')
        cursor.close()
        conn.close()
        return redirect(url_for('home'))

    # Get user's measurement history
    cursor.execute("""
        SELECT * FROM BodyMeasurement 
        WHERE UserID = %s 
        ORDER BY LogDate DESC
    """, (session['user_id'],))
    measurements = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('bodymeasurement.html', measurements=measurements, date=date)

@app.route('/nutritionlog', methods=['GET', 'POST'])
def nutritionlog():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch the user's goal
    cursor.execute("SELECT * FROM FitnessGoal WHERE UserID = %s", (session['user_id'],))
    goal = cursor.fetchone()

    if not goal:
        flash('Please set a fitness goal first!')
        cursor.close()
        conn.close()
        return redirect(url_for('fitnessgoal'))

    if request.method == 'POST':
        meal_type = request.form['meal_type']
        calories = request.form['calories']
        food_item = request.form['food_item']
        carbs = request.form['carbs']
        protein = request.form['protein']
        log_date = request.form.get('log_date', date.today().isoformat())

        # Get next LogID
        cursor.execute("SELECT MAX(LogID) FROM NutritionLog")
        result = cursor.fetchone()
        new_log_id = 401 if result['MAX(LogID)'] is None else result['MAX(LogID)'] + 1

        # Insert nutrition log
        cursor.execute("""
            INSERT INTO NutritionLog 
            (LogID, UserID, GoalID, MealType, Calories, FoodItem, Carbs, Protein, LogDate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (new_log_id, session['user_id'], goal['GoalID'], meal_type, calories, food_item, carbs, protein, log_date))

        conn.commit()
        flash('Nutrition log saved successfully!')
        cursor.close()
        conn.close()
        return redirect(url_for('home'))

    # Get user's nutrition history
    cursor.execute("""
        SELECT * FROM NutritionLog 
        WHERE UserID = %s 
        ORDER BY LogDate DESC
    """, (session['user_id'],))
    logs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('nutritionlog.html', logs=logs, date=date)

@app.route('/myworkoutplan')
def myworkoutplan():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT GoalID, GoalType FROM FitnessGoal WHERE UserID = %s", (session['user_id'],))
    goal = cursor.fetchone()
    if not goal or not goal['GoalType']:
        flash('Please set your fitness goal first!')
        cursor.close()
        conn.close()
        return redirect(url_for('fitnessgoal'))

    goal_type = goal['GoalType'].lower()
    cursor.close()
    conn.close()

    if goal_type == 'basic':
        return render_template('beginner-workout-plan.html')
    elif goal_type == 'intermediate':
        return render_template('intermediate-workout-plan.html')
    elif goal_type == 'advanced':
        return render_template('advanced-workout-plan.html')
    elif goal_type == 'expert':
        return render_template('expert-workout-plan.html')
    else:
        flash('Unknown goal type. Please set your fitness goal again.')
        return redirect(url_for('fitnessgoal'))

def calculate_bmi(weight, height):
    """Calculate BMI from weight(kg) and height(cm)"""
    height_m = height / 100
    bmi = weight / (height_m * height_m)
    return round(bmi, 1)

def get_bmi_category(bmi):
    """Return BMI category and health risk"""
    if bmi < 18.5:
        return "Underweight", "Risk of nutritional deficiency"
    elif bmi < 25:
        return "Normal weight", "Lowest risk"
    elif bmi < 30:
        return "Overweight", "Moderate risk"
    else:
        return "Obese", "High risk of health problems"

def analyze_body_fat(body_fat, gender):
    """Analyze body fat percentage"""
    if gender == 'M':
        if body_fat < 6:
            return "Essential fat", "Too low - health risks"
        elif body_fat < 14:
            return "Athletes", "Excellent"
        elif body_fat < 18:
            return "Fitness", "Good"
        elif body_fat < 25:
            return "Average", "Fair"
        else:
            return "Obese", "Need improvement"
    else:  # Female
        if body_fat < 13:
            return "Essential fat", "Too low - health risks"
        elif body_fat < 21:
            return "Athletes", "Excellent"
        elif body_fat < 25:
            return "Fitness", "Good"
        elif body_fat < 32:
            return "Average", "Fair"
        else:
            return "Obese", "Need improvement"

def get_fitness_recommendations(bmi_category, body_fat_category, goal_type):
    """Generate personalized fitness recommendations"""
    recommendations = []
    
    if bmi_category == "Underweight":
        recommendations.extend([
            "Focus on strength training to build muscle mass",
            "Increase caloric intake with nutrient-rich foods",
            "Include protein-rich foods in every meal"
        ])
    elif bmi_category == "Overweight" or bmi_category == "Obese":
        recommendations.extend([
            "Combine cardio and strength training",
            "Create a caloric deficit through diet and exercise",
            "Focus on portion control"
        ])
    
    if body_fat_category == "Athletes":
        recommendations.extend([
            "Maintain current fitness routine",
            "Focus on performance goals",
            "Ensure adequate recovery"
        ])
    elif body_fat_category in ["Average", "Obese"]:
        recommendations.extend([
            "Increase exercise frequency",
            "Add high-intensity interval training",
            "Monitor food intake closely"
        ])
    
    if goal_type.lower() == "basic":
        recommendations.extend([
            "Start with walking or light jogging",
            "Learn proper exercise form",
            "Gradually increase workout intensity"
        ])
    elif goal_type.lower() == "advanced":
        recommendations.extend([
            "Include progressive overload",
            "Try advanced workout techniques",
            "Consider splitting routines by muscle groups"
        ])
    
    return recommendations

@app.route('/generate_report')
def generate_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all required data
    cursor.execute("SELECT * FROM Users WHERE UserID = %s", (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute("SELECT * FROM FitnessGoal WHERE UserID = %s", (session['user_id'],))
    goals = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM BodyMeasurement 
        WHERE UserID = %s 
        ORDER BY LogDate DESC LIMIT 1
    """, (session['user_id'],))
    measurement = cursor.fetchone()

    cursor.execute("""
        SELECT AVG(CalorieBurnt) as avg_calories, 
               AVG(Duration) as avg_duration,
               COUNT(*) as workout_count
        FROM WorkoutProgram 
        WHERE UserID = %s 
        AND LogDate >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """, (session['user_id'],))
    workout_stats = cursor.fetchone()

    cursor.execute("""
        SELECT AVG(Calories) as avg_calories,
               AVG(Carbs) as avg_carbs,
               AVG(Protein) as avg_protein
        FROM NutritionLog
        WHERE UserID = %s 
        AND LogDate >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """, (session['user_id'],))
    nutrition_stats = cursor.fetchone()

    cursor.close()
    conn.close()

    # Create PDF with analysis
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Fitness Analysis Report', 0, 1, 'C')
    pdf.line(10, 30, 200, 30)
    
    # Personal Information
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Personal Information:', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f"Name: {user['Name']}", 0, 1)
    pdf.cell(0, 10, f"Report Date: {datetime.now().strftime('%Y-%m-%d')}", 0, 1)

    # Health Metrics Analysis
    if measurement:
        bmi = calculate_bmi(measurement['Weight'], measurement['Height'])
        bmi_category, health_risk = get_bmi_category(bmi)
        fat_category, fat_status = analyze_body_fat(measurement['BodyFatPercentage'], 'M')  # Assuming male for now

        pdf.ln(10)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'Health Metrics Analysis:', 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"BMI: {bmi} ({bmi_category})", 0, 1)
        pdf.cell(0, 10, f"Health Risk Assessment: {health_risk}", 0, 1)
        pdf.cell(0, 10, f"Body Fat Status: {fat_category} - {fat_status}", 0, 1)

    # Fitness Progress
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Fitness Progress:', 0, 1)
    pdf.set_font('Arial', '', 12)
    if workout_stats['workout_count']:
        pdf.cell(0, 10, f"Workout Frequency: {workout_stats['workout_count']} sessions/month", 0, 1)
        pdf.cell(0, 10, f"Average Workout Duration: {round(workout_stats['avg_duration'], 1)} minutes", 0, 1)
        pdf.cell(0, 10, f"Average Calories Burnt: {round(workout_stats['avg_calories'], 1)} kcal/session", 0, 1)

    # Nutrition Analysis
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Nutrition Analysis:', 0, 1)
    pdf.set_font('Arial', '', 12)
    if nutrition_stats['avg_calories']:
        pdf.cell(0, 10, f"Average Daily Calories: {round(nutrition_stats['avg_calories'], 1)} kcal", 0, 1)
        pdf.cell(0, 10, f"Average Daily Carbs: {round(nutrition_stats['avg_carbs'], 1)}g", 0, 1)
        pdf.cell(0, 10, f"Average Daily Protein: {round(nutrition_stats['avg_protein'], 1)}g", 0, 1)

    # Recommendations
    if measurement and goals:
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'Personalized Recommendations:', 0, 1)
        pdf.set_font('Arial', '', 12)
        recommendations = get_fitness_recommendations(bmi_category, fat_category, goals['GoalType'])
        for rec in recommendations:
            pdf.cell(0, 10, f"- {rec}", 0, 1)

    # Generate PDF
    pdf_output = pdf.output(dest='S').encode('latin-1')
    
    return send_file(
        io.BytesIO(pdf_output),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'fitness_analysis_{datetime.now().strftime("%Y%m%d")}.pdf'
    )

if __name__ == '__main__':
    app.run(debug=True)