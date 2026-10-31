


# What's in the picture?

**A real-time object detection demo built on [Roboflow](https://roboflow.com).** Pick one of about 1,800 sample photos, or upload your own, and watch the AI outline everything it finds, with a label and confidence score on every box.

**Live demo:** https://davidcarroll.cloud/roboflow/

<!-- Add a screenshot or short demo GIF here, for example: ![Demo](docs/demo.gif) -->
https://github.com/user-attachments/assets/15bb7e32-42ee-4f9e-8bdf-1f602e79d578
<!-- Add a screenshot or short demo GIF here, for example: ![Demo](docs/demo.gif) -->

## What it does

- Browse a paged grid of sample photos and click one to run detection on it.
- See bounding boxes drawn over the image in real time, each with a class name and confidence percentage.
- Upload your own photo. Uploads are checked live and **never saved**.
- Boxes below a confidence threshold are hidden (50% by default).

## How it works

```
Browser  -->  Flask server  -->  Roboflow (rfdetr-base)
   ^               |
   |               +--> saved results, so each sample is only checked once
   +-- sample photos served through Amazon CloudFront
```

- **Front end:** a single HTML page with plain JavaScript. It draws the image and the boxes on a canvas.
- **Back end:** a small [Flask](https://flask.palletsprojects.com) app that keeps the Roboflow API key on the server, so it never reaches the browser.
- **Saved results:** the first time someone clicks a sample, the server asks Roboflow and saves the answer. Every later click reuses it, which keeps it fast and avoids spending Roboflow credits.
- **Alerts:** an optional email through Amazon SES whenever someone views a sample or uploads a photo.
- **Admin page:** a password-protected page for removing samples. Deleted photos move to a `trash` folder rather than being erased.

## Files

| File | What it is |
| --- | --- |
| `index.html` | The public app page |
| `server.py` | The Flask back end |
| `admin.html` | Admin page for reviewing and removing samples |

## Setup

1. Install the dependencies:

   ```
   pip install flask inference-sdk pillow boto3
   ```

2. Put your sample photos in an `images` folder next to `server.py`. (Photos are not included in this repo.)

3. Set your environment variables, for example in `/etc/roboflow.env`:

   | Variable | Purpose |
   | --- | --- |
   | `ROBOFLOW_API_KEY` | Your Roboflow API key (required) |
   | `ADMIN_PASSWORD` | Password for deleting samples. Deleting is switched off if unset |
   | `ALERT_TO`, `ALERT_FROM` | Email addresses for SES alerts |
   | `SES_REGION` | AWS region for SES (default `us-east-1`) |
   | `IGNORE_IPS` | Comma-separated IPs that should never trigger an alert |

4. Update the settings at the top of the script in `index.html`, especially `SAMPLES_DIR`, which should point at wherever your sample photos are served from.

5. Run it:

   ```
   python server.py
   ```

   For anything public-facing, run it behind a proper WSGI server such as gunicorn rather than Flask's built-in debug server.

## Customising

- **Model:** change `MODEL_ID` in `server.py` and `index.html` to use a different Roboflow model.
- **Confidence cut-off:** change `MIN_CONF` in `index.html`.
- **Thumbnails per page:** change `PER_PAGE` in `index.html`.

## Notes on the sample photos

The demo's samples come from the [COCO dataset](https://cocodataset.org), as published on Roboflow Universe. COCO images have their own licences, so check its terms before reusing or redistributing them.

## Credits --

Built with [Roboflow](https://roboflow.com), [Flask](https://flask.palletsprojects.com) and [Amazon CloudFront](https://aws.amazon.com/cloudfront/).
