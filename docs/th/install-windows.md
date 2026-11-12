# ติดตั้งบน Windows

[English](../en/install-windows.md) | [ภาษาไทย](install-windows.md)

SD-Scripts GUI ทำงานบน Windows ด้วยไฟล์ batch สองไฟล์กับ [uv](https://docs.astral.sh/uv/) ไม่มีตัวติดตั้งและไม่มีไฟล์ `.exe`

## ความต้องการของระบบ

| รายการ | ความต้องการ |
|---|---|
| ระบบปฏิบัติการ | Windows 10 หรือ 11 แบบ 64-bit |
| GPU | NVIDIA พร้อม driver ที่รองรับ CUDA 12.8 |
| พื้นที่ดิสก์ | ว่างประมาณ 25 GB สำหรับ environment รวมกับโมเดลของคุณ |
| อินเทอร์เน็ต | ใช้ตอนติดตั้งและตอนดาวน์โหลดโมเดล |
| uv | `winget` จะติดตั้งให้อัตโนมัติถ้ายังไม่มี หรือ[ติดตั้ง uv](https://docs.astral.sh/uv/getting-started/installation/) เอง |
| git | ไม่บังคับ ถ้าไม่มี `install.bat` จะดาวน์โหลด sd-scripts เป็นไฟล์ zip แทน (แต่จะตรวจ commit ของ schema ไม่ได้) |
| WebView2 | หน้าต่างเดสก์ท็อปต้องใช้ มีมาให้แล้วใน Windows 11 ถ้าไม่มีให้ใช้ `run-browser.bat` |

## ติดตั้ง

1. ดาวน์โหลด `sd-scripts-gui-vX.Y.Z.zip` จาก [GitHub Releases](https://github.com/vjumpkung/vjump-sd-scripts-gui/releases) หรือจะ clone repository ก็ได้ ดูหมายเหตุด้านล่าง
2. แตกไฟล์ไปไว้ใน path สั้น ๆ ที่เป็นตัวอักษร ASCII ล้วน เช่น `C:\sd-gui` หลีกเลี่ยงโฟลเดอร์ที่มีช่องว่าง ตัวอักษรไทย หรือชื่อยาวมาก
3. ดับเบิลคลิก `install.bat`

`install.bat` ทำงานตามนี้ และรันซ้ำได้อย่างปลอดภัยเสมอ

| ขั้นตอน | สิ่งที่เกิดขึ้น |
|---|---|
| uv | ติดตั้งด้วย `winget` ถ้ายังไม่มี |
| Python | Python 3.12 ที่ uv จัดการให้ |
| sd-scripts | clone จาก `vjumpkung/sd-scripts` (branch `feat/vjump`) ไปไว้ใน `sd-scripts\` |
| Environment | virtual environment ที่ `sd-scripts\venv` |
| PyTorch | `torch 2.8.0` แบบ CUDA 12.8 (`+cu128`) และ requirements ของ sd-scripts ขนาดหลาย GB ถ้า torch ที่ลงเสร็จเป็นแบบ CPU สคริปต์จะหยุดพร้อมแจ้งข้อผิดพลาด |
| Backend | `uv sync` ของ backend พร้อม desktop extra ลงใน `backend\.venv` |
| Frontend | ไฟล์ zip ของ release มี frontend ที่ build แล้วอยู่ในตัว |
| Workspace | สร้างโฟลเดอร์ `workspace\` |

> ถ้า clone repository แทนการใช้ไฟล์ zip จะไม่มี frontend ที่ build แล้ว (`backend\web`) เพราะไม่ได้เก็บใน git ให้ติดตั้ง Node.js และ [pnpm](https://pnpm.io/installation) ก่อน แล้ว `install.bat` จะ build ให้เอง

ตัวเลือกเสริมของ `install.bat` ให้ตั้งค่าก่อนรัน (เช่น `set UPDATE=1`)

| ตัวแปร | ความหมาย |
|---|---|
| `UPDATE=1` | ดึง commit ล่าสุดของ sd-scripts เข้ามาใน clone ที่มีอยู่แล้วใน `sd-scripts\` |
| `SD_SCRIPTS_REPO`, `SD_SCRIPTS_REF` | ใช้ fork หรือ branch อื่นของ sd-scripts |
| `TORCH_VERSION`, `TORCHVISION_VERSION`, `TORCH_INDEX_URL` | ใช้ PyTorch build อื่น |
| `NO_PAUSE=1` | ไม่รอให้กดปุ่มตอนจบ |

## เปิดใช้งาน

| ไฟล์ | ผลลัพธ์ |
|---|---|
| `run.bat` | เปิดแอปในหน้าต่างเดสก์ท็อปของตัวเอง |
| `run-browser.bat` | เริ่มเซิร์ฟเวอร์แล้วเปิดเบราว์เซอร์ที่ `http://127.0.0.1:8000` |

ใช้ `run-browser.bat` เมื่อหน้าต่างเดสก์ท็อปไม่เปิด เช่น ไม่มี WebView2 ถ้าอยากเปลี่ยน port ให้ตั้ง `SD_SCRIPTS_GUI_PORT` ก่อน เช่น `set SD_SCRIPTS_GUI_PORT=8100`

ปิดหน้าต่าง หรือกด `Ctrl+C` ในหน้าต่าง console ของ `run-browser.bat` เพื่อหยุด การหยุดแอปจะหยุดงานเทรนที่กำลังทำงานอยู่ด้วย

แอปเข้าถึงได้จากเครื่องนี้เท่านั้น (`127.0.0.1`) และหน้าต่างเดสก์ท็อปจะจำการตั้งค่าและ draft ไว้ข้ามการเปิดแต่ละครั้ง

## อัปเดต

1. ดาวน์โหลดไฟล์ zip ของ release ใหม่ แล้วแตกทับโฟลเดอร์เดิม โฟลเดอร์ `workspace\` และ `backend\data\` ไม่ได้อยู่ในไฟล์ zip โมเดล dataset ผลลัพธ์ และประวัติงานของคุณจึงยังอยู่ครบ หรือถ้า clone repository ไว้ ให้รัน `git pull`
2. รัน `install.bat` อีกครั้ง มันจะติดตั้งเฉพาะสิ่งที่เปลี่ยน
3. ถ้าต้องการอัปเดต sd-scripts ด้วย ให้รันพร้อม `UPDATE=1`

   ```bat
   set UPDATE=1
   install.bat
   ```

4. เปิดแอป ถ้ามีแถบแจ้งว่า argument schema ล้าสมัย ให้เปิดหน้า **ตั้งค่า** แล้วกด **สแกนอาร์กิวเมนต์ใหม่ (Rescan)** ดู[ตั้งค่า](settings.md)

## ทำไมไม่มีไฟล์ `.exe`

ไฟล์ปฏิบัติการที่ไม่ได้ลงนามดิจิทัลมักถูกโปรแกรมแอนตี้ไวรัสกักกัน ไฟล์ `.bat` กับ uv เลี่ยงปัญหานี้ได้ และคุณอ่านทุกบรรทัดของมันได้ก่อนรัน

## ถอนการติดตั้ง

ลบโฟลเดอร์ทิ้ง ทุกอย่างที่แอปติดตั้งอยู่ในโฟลเดอร์นั้น ยกเว้น cache ของ uv และ Python ที่ uv จัดการ ถ้าติดตั้ง uv ด้วย winget สามารถถอนได้ด้วย `winget uninstall astral-sh.uv`

ถัดไป: [เริ่มต้นใช้งาน](quick-start.md)
