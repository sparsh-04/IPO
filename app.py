import os
from flask import Flask, request, redirect, url_for, render_template, flash
from werkzeug.utils import secure_filename
import pandas as pd
import csv
import requests
from bs4 import BeautifulSoup
import logging
from io import StringIO

UPLOAD_FOLDER = '/tmp/uploads'
DATA_FOLDER = '/tmp/data'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATA_FOLDER'] = DATA_FOLDER
app.secret_key = 'supersecretkey'  # Needed for flashing messages
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

if not os.path.exists(app.config['DATA_FOLDER']):
    os.makedirs(app.config['DATA_FOLDER'])

# Configure logging
logging.basicConfig(level=logging.INFO)

def scrapper(urls, output_file):
    def process_url(url):
        response = requests.get(url)
        if response.status_code == 200:
            start = url.find("ipo/") + len("ipo/")
            if url.find("sme-ipo") != -1:
                end = url.find("-sme-ipo", start)
                sme = True
            else:
                end = url.find("-ipo", start)
                sme = False
            ipo_name = url[start:end]
            soup = BeautifulSoup(response.content, 'html.parser')
            tables = soup.find_all('table')
            for i, table in enumerate(tables):
                df = pd.read_html(StringIO(str(table)))[0]
                if i == 2 and not sme:
                    r_lot_value = df.iloc[2].array[1]
                    r_lot_value = r_lot_value.replace("₹", "").replace(",", "")
                    r_lot_value = int(r_lot_value)
                    shni = 200000 // r_lot_value
                    if shni * r_lot_value < 200000:
                        shni += 1
                    bhni = 1000000 // r_lot_value
                    if bhni * r_lot_value < 1000000:
                        bhni += 1
                if i==2 and sme:
                    r_lot_value = df.iloc[2].array[1]
                    r_lot_value = r_lot_value.replace("₹", "").replace(",", "")
                    r_lot_value = int(r_lot_value)
                    shni = bhni = 2
                    
                if i == 3:
                    GMP = str(df.iloc[0].array[4])
                    GMP = GMP.split('(', 1)[1].split(')')[0][0:-1]
                    GMP = float(GMP)
                if i == 5 and not sme:
                    r_sub = float(df.iloc[-1].array[6].replace("x", "").replace(",", ""))
                    s_sub = float(df.iloc[-1].array[4].replace("x", "").replace(",", ""))
                    b_sub = float(df.iloc[-1].array[5].replace("x", "").replace(",", ""))
                    
                if i == 5 and sme:
                    r_sub = float(df.iloc[-1].array[4].replace("x", "").replace(",", ""))
                    s_sub = float(df.iloc[-1].array[3].replace("x", "").replace(",", ""))
                    b_sub = float(df.iloc[-1].array[3].replace("x", "").replace(",", ""))
            with open(output_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([GMP, r_lot_value, shni * r_lot_value, bhni * r_lot_value, r_sub, s_sub, b_sub, ipo_name,sme])
        else:
            logging.error(f"Failed to fetch the page. Status code: {response.status_code}")

    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["GMP", "r_lot_value", "shni", "bhni", "r_sub", "s_sub", "b_sub", "ipo_name", "sme"])

    for url in urls:
        url = url.strip()
        if url:
            process_url(url)

def read_csv_to_array(csv_file):
    data = []
    with open(csv_file, mode='r') as file:
        reader = csv.reader(file)
        for row in reader:
            data.append(row)
    return data

def iterative(data, max_cash, output_file, max_account):
    stack = [(1, 0, 0, 0, [])]
    column_names = ['r_lot', 'shni', 'bhni']
    results = []
    while stack:
        i, j, expected_profit, money_used, selected_columns = stack.pop()
        if i == len(data):
            results.append((expected_profit, money_used, selected_columns))
        else:
            # for _ in range(1, max_account+1):
            # print(max_account)
            if data[i][8]=="False":
                for j in range(0, 4):
                    if j == 0:
                        new_expected_profit = expected_profit
                        new_selected_columns = selected_columns + ['0']
                        new_money_used = money_used
                        stack.append((i + 1, j, new_expected_profit, new_money_used, new_selected_columns))
                        continue

                    elif float(data[i][j + 3]) <= 1:
                        new_expected_profit = expected_profit + float(data[i][j]) * (1 + float(data[i][0]) / 100)
                    else:
                        new_expected_profit = expected_profit + float(data[i][j]) * (1 + float(data[i][0]) / 100) / float(data[i][j + 3]) + float(data[i][j])*(1-1/float(data[i][j + 3]))
                    new_selected_columns = selected_columns + [column_names[j - 1]]
                    new_money_used = money_used + float(data[i][j])
                    stack.append((i + 1, j, new_expected_profit, new_money_used, new_selected_columns))
            elif data[i][8]=="True":
                    for j in range(0, 8):
                        if j == 0:
                            new_expected_profit = expected_profit
                            new_selected_columns = selected_columns + ['0']
                            new_money_used = money_used
                            stack.append((i + 1, j, new_expected_profit, new_money_used, new_selected_columns))
                            continue
                        if j==1:
                            new_expected_profit = expected_profit + float(data[i][1]) * (1 + float(data[i][0]) / 100) / float(data[i][4]) + float(data[i][1])*(1-1/float(data[i][4]))
                        else:
                            new_expected_profit = expected_profit + float(data[i][1]) * j * (1 + float(data[i][0]) / 100) / float(data[i][5]) + float(data[i][1])*j*(1-1/float(data[i][5]))
                        new_selected_columns = selected_columns + [f'{j}x']
                        new_money_used = money_used + float(data[i][1])*j
                        stack.append((i + 1, j, new_expected_profit, new_money_used, new_selected_columns))
    sorted_results = sorted(results, key=lambda x: x[0], reverse=True)
    with open(output_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        ipo_names = [data[i][7] for i in range(1, len(data))]
        ipo_names = ', '.join(ipo_names)

        # Join the values into a single string, separated by commas

        writer.writerow(['Expected Profit', 'Money Used', f'{ipo_names}'])
        for result in sorted_results:
            expected_profit, money_used, selected_columns = result
            if money_used < max_cash and money_used > 0:
                writer.writerow([expected_profit, money_used, ', '.join(selected_columns)])

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            urls = request.form['urls'].splitlines()
            file = request.files.get('file')
            if file and file.filename != '':
                file_urls = file.read().decode('utf-8').splitlines()
                urls.extend(file_urls)
            max_cash = request.form['max_cash']
            max_account = request.form['max_account']
            output_file = os.path.join(app.config['DATA_FOLDER'], 'a.csv')
            scrapper(urls, output_file)
            with open(output_file, mode='r') as file:
                contents = file.read()
                print(contents)
            data = read_csv_to_array(output_file)
            header = data[0]
            rows = data[1:]
            for _ in range(int(max_account)-1):
                data.extend(rows)
            print(data)
            temp_output_file = os.path.join(app.config['DATA_FOLDER'], 'temp.csv')
            # for _ in range(0, int(max_account)):
            iterative(data, float(max_cash), temp_output_file, int(max_account))
            return redirect(url_for('results'))
        except Exception as e:
            logging.error(f"Error processing request: {e}")
            flash("An error occurred while processing your request. Please try again.")
            return redirect(url_for('index'))
    return render_template('index.html')


@app.route('/results')
def results():
    temp_output_file = os.path.join(app.config['DATA_FOLDER'], 'temp.csv')
    results = []
    try:
        with open(temp_output_file, mode='r') as file:
            reader = csv.reader(file)
            for row in reader:
                results.append(row)
    except Exception as e:
        logging.error(f"Error reading results: {e}")
        flash("An error occurred while reading the results. Please try again.")
        return redirect(url_for('index'))
    return render_template('results.html', results=results)


if __name__ == '__main__':
    app.run()