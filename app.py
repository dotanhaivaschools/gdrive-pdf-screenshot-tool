import streamlit as st
import time
import os
import tempfile
from PIL import Image, ImageChops
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# ========= Cấu hình Chrome headless cho Render =========
def launch_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    options.binary_location = os.getenv("GOOGLE_CHROME_BIN", "/usr/bin/chromium-browser")
    return webdriver.Chrome(
        executable_path=os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver"),
        options=options
    )

# ========= Crop viền ảnh =========
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

def find_pdf_region(driver):
    from selenium.webdriver.common.by import By
    for sel in ['div[role="main"]', 'canvas', 'embed', 'iframe']:
        try:
            return driver.find_element(By.CSS_SELECTOR, sel)
        except:
            continue
    return None

def capture_region(driver, index, temp_dir):
    from selenium.webdriver.common.by import By
    path = os.path.join(temp_dir, f"page_{index}.png")
    full = os.path.join(temp_dir, "tmp_full.png")
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

# ========= Giao diện Streamlit =========
st.set_page_config(page_title="Chụp PDF từ Google Drive", layout="centered")
st.title("📄 Chụp PDF từ Google Drive (Render-ready)")

if "driver" not in st.session_state:
    st.session_state.driver = None
    st.session_state.temp_dir = tempfile.mkdtemp()
    st.session_state.images = []
    st.session_state.last_image = None
    st.session_state.deleted = set()

link = st.text_input("🔗 Dán link Google Drive Viewer")
if st.button("🚀 Mở Google Drive"):
    try:
        driver = launch_driver()
        driver.get(link)
        time.sleep(5)
        st.session_state.driver = driver
        st.success("✅ Trình duyệt đã sẵn sàng. Cuộn và chụp trang PDF.")
    except Exception as e:
        st.error(f"Lỗi khi mở trình duyệt: {e}")

if st.session_state.driver:
    if st.button("📸 Chụp trang"):
        idx = len(st.session_state.images)
        path = capture_region(st.session_state.driver, idx, st.session_state.temp_dir)
        if st.session_state.last_image and is_duplicate_image(path, st.session_state.last_image):
            os.remove(path)
            st.warning("⚠️ Trang này trùng với ảnh trước đó.")
        else:
            st.session_state.last_image = path
            st.session_state.images.append(path)
            st.toast(f"✅ Đã chụp trang {len(st.session_state.images)}")

if st.session_state.images:
    st.markdown("### 📸 Ảnh đã chụp")
    keep_images = []
    for i, p in enumerate(st.session_state.images):
        if i not in st.session_state.deleted:
            st.image(p, caption=f"Trang {len(keep_images) + 1}", use_container_width=True)
            if st.button(f"🗑️ Xóa Trang {len(keep_images) + 1}", key=f"delete_{i}"):
                st.session_state.deleted.add(i)
        else:
            continue
        keep_images.append(p)

    if st.button("✅ Tạo PDF"):
        try:
            valid = [crop_border(Image.open(p).convert("RGB")) for i, p in enumerate(st.session_state.images) if i not in st.session_state.deleted]
            output_path = os.path.join(st.session_state.temp_dir, "output.pdf")
            valid[0].save(output_path, save_all=True, append_images=valid[1:])
            with open(output_path, "rb") as f:
                st.download_button("📥 Tải PDF", f, file_name="converted.pdf")
        except Exception as e:
            st.error(f"Lỗi tạo PDF: {e}")