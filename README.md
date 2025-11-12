# 🖼️ VisionLabel — Image Label Generator using AWS Rekognition

**VisionLabel** is a Flask web application that lets users upload an image and automatically detects objects within it using **AWS Rekognition**.  
The app draws **bounding boxes** and **confidence scores** around detected objects, returning both the labeled and original images.

🌐 **Live Demo:** [https://visionlabel.onrender.com](https://visionlabel.onrender.com)

---

## 🚀 Features

- Upload JPG/PNG images directly from your browser.
- Detect and label objects using **Amazon Rekognition**.
- Draw bounding boxes with confidence percentages.
- Modern Bootstrap-based UI with drag-and-drop upload.
- Option for **local dry-run mode** (no AWS required).
- Deployed on **Render (Free Tier)** with automatic scaling.

---

## 🧰 Tech Stack

| Category | Technology |
|-----------|-------------|
| **Backend** | Python, Flask, Gunicorn |
| **Frontend** | HTML, CSS, Bootstrap 5 |
| **Cloud AI** | AWS Rekognition |
| **Hosting** | Render (Free Tier) |
| **Image Processing** | Pillow (PIL) |
| **Storage** | Local `static/uploads` folder (or S3 for persistence) |

---
