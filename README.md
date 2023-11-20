Major architectural and other changes here. The below videos may not work.

Here are the steps to run:

* Checkout this repo in a folder
* create virtual environment
* activate the virual environment
* run => python3 -m pip install -U pip
* run => sudo apt-get install libpq-dev python-dev
* run => pip install flask flask_session numpy psycopg2-binary py_vollib_vectorized kiteconnect plotly
* update the folder path in server.json, ensure the deploy folder and logs folder exist
* Download and install questdb from here => https://questdb.io/download/
* copy the sample.json into **some-other-short-code**.json eg 1234.json and add the keys etc from zerodha api setup
* cd into src folder, run => flask run main.py
* start questdb [required for range breakouts]
* access your application on http://localhost:8080/me/some-other-short-code
* Added a Test Algo with strategies from https://www.youtube.com/watch?v=GSJHDZmyHaY



# sdoosa-algo-trade-python

This project is mainly for newbies into algo trading who are interested in learning to code their own trading algo using python interpreter.

This is in the context of Indian stock exchanges and brokers.

Here is the youtube playlist with 10+ videos explaining the whole project with live trading demo.

https://www.youtube.com/playlist?list=PL-yBsBIJqqBn6oMMgLjvhCTNT-zLXYmoW
