import streamlit as st
import time
import os
import tempfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from PIL import Image, ImageChops

st.set_page_config(page_title="Chụp PDF từ Google Drive", layout="centered")
st.title("📄 Chụp PDF từ Google Drive (Render-ready)")

# Giao diện nhập link
link = st.text_input("🔗 Dán link Google Drive Viewer:")
start = st.button("🚀 Mở Google Drive")

# Khởi tạo session
if "driver" not in st.session_state:
    st.session_state.driver = None
    st.session_state.temp_dir = tempfile.mkdtemp()
    st.session_state.last_image_path = None
    st.session_state.image_count = 0
    st.session_state.captured_images = []
    st.session_state.to_delete = []

# ---------- Chức năng chính ----------

def crop_border(image, threshold=240):
    gray = image.convert("L")
    bw = gray.point(lambda x: 255 if x > threshold else 0, mode='1')
    bbox = bw.getbbox()
    return image.crop(bbox) if bbox else image

def is_duplicate_image(img1_path, img2_path):
    try:
        img1 = Image.open(img1_path).resize((300, 300)).convert("L")
        img2 = Image.open(img2_path).resize((300, 300)).convert("L")
        diff = ImageChops.difference(img1, img2)
        return diff.getbbox() is None
    except:
        return False

def launch_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

def find_pdf_region(driver):
    for sel in ['div[role="main"]', 'canvas', 'embed', 'iframe']:
        try:
            return driver.find_element(By.CSS_SELECTOR, sel)
        except:
            continue
    return None

def capture_region(driver, index):
    path = os.path.join(st.session_state.temp_dir, f"page_{index}.png")
    full = os.path.join(st.session_state.temp_dir, "tmp_full.png")
    driver.save_screenshot(full)

    region = find_pdf_region(driver)
    if not region:
        os.rename(full, path)
        return path

    loc = region.location_once_scrolled_into_view
    size = region.size
    x, y = int(loc["x"]), int(loc["y"])
    w, h = int(size["width"]), int(size["height"])
    img = Image.open(full)
    cropped = img.crop((x, y, x + w, y + h))
    cropped.save(path)
    return path

def capture_and_store():
    idx = st.session_state.image_count
    path = capture_region(st.session_state.driver, idx)
    if st.session_state.last_image_path and is_duplicate_image(path, st.session_state.last_image_path):
        os.remove(path)
        st.warning("⚠️ Trang này đã được chụp rồi (trùng ảnh trước).")
    else:
        st.session_state.last_image_path = path
        st.session_state.captured_images.append(path)
        st.session_state.image_count += 1
        st.toast(f"✅ Đã chụp trang {st.session_state.image_count}")

# ---------- Giao diện ----------

if start and link:
    try:
        driver = launch_driver()
        driver.get(link)
        time.sleep(5)
        st.session_state.driver = driver
        st.success("✅ Đã mở trình duyệt thành công!")
    except Exception as e:
        st.error(f"Lỗi khi mở trình duyệt: {e}")

if st.session_state.driver:
    if st.button("📸 Chụp"):
        capture_and_store()

    if st.session_state.captured_images:
        st.markdown("### 🖼️ Các trang đã chụp:")
        for i, img_path in enumerate(st.session_state.captured_images):
            if i not in st.session_state.to_delete:
                st.image(img_path, caption=f"Trang {i+1}", use_container_width=True)
                col1, _ = st.columns([1, 5])
                with col1:
                    if st.button(f"🗑️ Xóa ảnh Trang {i+1}", key=f"delete_{i}"):
                        st.session_state.to_delete.append(i)
                        st.rerun()

        # Nút xoá tất cả ảnh đã loại
        if st.session_state.to_delete:
            if st.button("🧹 Xóa các ảnh đã loại"):
                st.session_state.captured_images = [
                    p for i, p in enumerate(st.session_state.captured_images)
                    if i not in st.session_state.to_delete
                ]
                st.session_state.to_delete = []
                st.rerun()

        if st.button("✅ Tạo file PDF"):
            try:
                images = [
                    crop_border(Image.open(p).convert("RGB"))
                    for i, p in enumerate(st.session_state.captured_images)
                    if i not in st.session_state.to_delete
                ]
                output_path = os.path.join(st.session_state.temp_dir, "converted.pdf")
                images[0].save(output_path, save_all=True, append_images=images[1:])
                with open(output_path, "rb") as f:
                    st.download_button("📥 Tải PDF", f, file_name="converted.pdf")
            except Exception as e:
                st.error(f"Lỗi khi tạo PDF: {e}")
    else:
        st.info("📌 Hãy chụp ít nhất một trang để tạo PDF.")
