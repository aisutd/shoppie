"""Minimal Flask app wrapping the lesson pipeline. Run from repo root: python -m webapp.app"""

from flask import Flask, flash, redirect, render_template, request, url_for
from pydantic import ValidationError

from lesson.extract import extract_product
from lesson.pages import fetch_page, fetch_rendered_page
from lesson.validate import Laptop

app = Flask(__name__)
app.secret_key = "dev-classroom-not-a-secret"


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/extract")
def extract():
    url = request.form.get("url", "").strip()
    if not url:
        flash("Enter a retailer URL.", "error")
        return redirect(url_for("index"))

    try:
        if request.form.get("browser") == "on":
            html = fetch_rendered_page(url)
        else:
            html = fetch_page(url)
        record = extract_product(html, url)
        validated = Laptop.model_validate(record)
    except ValueError as error:
        flash(f"Extraction refused: {error}", "error")
        return redirect(url_for("index"))
    except ValidationError as error:
        flash(f"Validation failed: {error}", "error")
        return redirect(url_for("index"))

    flash("ACCEPTED: required fields passed validation.", "ok")
    return render_template("product.html", record=validated)


if __name__ == "__main__":
    app.run(debug=True)
