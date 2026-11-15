# Cloud: Runpod และ Vast.ai

[English](../en/cloud-runpod-vast.md) | [ภาษาไทย](cloud-runpod-vast.md)

Docker image รัน GUI และ JupyterLab คู่กัน สร้างบน Ubuntu ธรรมดา เพราะ PyTorch wheel แบบ `cu128` มี CUDA มาในตัวอยู่แล้ว แต่ driver ของเครื่อง host ยังต้องรองรับ CUDA 12.8 เพื่อให้การเทรนใช้ GPU ได้

## Image

| รายการ | ค่า |
|---|---|
| Image | `ghcr.io/vjumpkung/vjump-sd-scripts-gui:latest` (มี tag `X.Y.Z`, `X.Y` และ commit ด้วย) |
| Port ของ GUI | `8000` |
| Port ของ JupyterLab | `8888` |
| Volume | mount พื้นที่เก็บข้อมูลถาวรที่ `/workspace` |

Environment variable

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `SD_SCRIPTS_GUI_PASSWORD` | ไม่ตั้ง | รหัสผ่านสำหรับหน้าเข้าสู่ระบบของ GUI ถ้าไม่ตั้ง container จะสร้างรหัสผ่านสุ่มทุกครั้งที่เริ่มและแสดงใน log ของ container ตั้งค่านี้เพื่อใช้รหัสผ่านที่คุณเลือกเอง ดู[รหัสผ่าน](#รหัสผ่าน) |
| `SD_SCRIPTS_GUI_ALLOW_NO_AUTH` | ไม่ตั้ง | `1` ปิดรหัสผ่านของ GUI ใช้เฉพาะเมื่ออยู่หลัง proxy ของคุณเองที่ยืนยันตัวตนผู้ใช้อยู่แล้ว |
| `JUPYTER_PASSWORD` | ไม่ตั้ง | token ของ JupyterLab ถ้าไม่ตั้ง Jupyter จะสร้าง token สุ่มแล้วแสดงใน log ของ container ค่านี้ส่งให้ Jupyter ผ่าน environment จึงไม่โผล่ใน `ps` |
| `ENABLE_JUPYTER` | `1` | ตั้งเป็น `0` เพื่อปิด JupyterLab |
| `SD_SCRIPTS_GUI_MCP` | `1` | `0` ปิด endpoint MCP (`/api/mcp`) สำหรับ AI agent ดู [MCP สำหรับ AI agent](#mcp-สำหรับ-ai-agent) |
| `PORT` | `8000` | port ของ GUI |
| `JUPYTER_PORT` | `8888` | port ของ JupyterLab |
| `HF_TOKEN` | ไม่ตั้ง | Hugging Face token โหลดเข้า secret store ในหน่วยความจำตอนเริ่ม จำเป็นสำหรับ[โมเดลที่ต้องขอสิทธิ์](downloads.md) |
| `WANDB_API_KEY` | ไม่ตั้ง | key ของ Weights & Biases ทำงานแบบเดียวกัน |

## Runpod

วิธีที่เร็วที่สุดคือใช้ template สำเร็จรูป: [SD-Scripts GUI Runpod template](https://console.runpod.io/hub/template/pi4l66uzj9?ref=6h6f9kga) ซึ่งตั้งค่าตามตารางด้านล่างไว้แล้ว เลือก GPU และขนาด volume แล้ว deploy ได้เลย

ถ้าต้องการตั้งค่าเอง ให้สร้าง template (หรือ pod ที่ใช้ค่าเดียวกัน)

| ช่อง | ค่า |
|---|---|
| Container image | `ghcr.io/vjumpkung/vjump-sd-scripts-gui:latest` |
| Expose HTTP ports | `8000,8888` |
| Volume mount path | `/workspace` |
| Environment variables | `SD_SCRIPTS_GUI_PASSWORD` (แนะนำ), `JUPYTER_PASSWORD` และ `HF_TOKEN` (ถ้าต้องการ) |

อย่าใส่รหัสผ่านที่ตายตัวหรือใช้ร่วมกันไว้ใน template ที่เผยแพร่ ให้เว้น `SD_SCRIPTS_GUI_PASSWORD` ไว้ แล้วแต่ละ pod จะสร้างรหัสผ่านของตัวเอง

ขนาด volume ให้เผื่อตามโมเดลที่จะดาวน์โหลด ดูขนาดในหน้า[ดาวน์โหลด](downloads.md)

เมื่อ pod ทำงานแล้ว เปิด GUI ผ่าน proxy ของ Runpod

```
https://<POD_ID>-8000.proxy.runpod.net
```

และเปิด JupyterLab ที่ `https://<POD_ID>-8888.proxy.runpod.net` ทั้งสอง URL แสดงอยู่ใน log ของ container ด้วย ถ้าไม่ได้ตั้ง `SD_SCRIPTS_GUI_PASSWORD` รหัสผ่านที่สร้างให้จะอยู่ใน log เดียวกัน: เปิดแท็บ **Logs** ของ pod แล้วหาบรรทัด `GUI password: ...`

## Vast.ai

1. เลือก template หรือสร้างใหม่ด้วย image `ghcr.io/vjumpkung/vjump-sd-scripts-gui:latest`
2. ใช้โหมดเปิดเครื่องแบบ **Docker ENTRYPOINT** image จะเริ่มทำงานเอง ถ้าจะใช้ on-start script ให้สั่งรัน `/start.sh`
3. map port `8000` และ `8888` (เช่น `-p 8000:8000 -p 8888:8888` ในตัวเลือก Docker)
4. ตั้ง environment variable ตามตารางด้านบน แนะนำให้ตั้ง `SD_SCRIPTS_GUI_PASSWORD` ถ้าไม่ตั้ง container จะสร้างรหัสผ่านให้และแสดงใน log ของ instance
5. ให้ instance มีดิสก์พอสำหรับโฟลเดอร์ `/workspace`

Vast.ai แสดง address และ port ภายนอกของแต่ละ port ที่ map ไว้ในหน้าจอของ instance ให้เปิดอันที่ map ไปยัง `8000` ถ้าไม่ได้ตั้งรหัสผ่าน รหัสผ่านที่สร้างให้อยู่ใน log ของ instance (`GUI password: ...`)

## รหัสผ่าน

GUI **ปลอดภัยตั้งแต่ค่าเริ่มต้น** port บน Vast.ai เป็นสาธารณะ container จึงไม่เปิด GUI แบบไม่มีรหัสผ่านเอง

| สิ่งที่คุณตั้ง | ผลลัพธ์ |
|---|---|
| ไม่ตั้งอะไร | สร้างรหัสผ่านสุ่ม**ทุกครั้งที่เริ่ม** และแสดงใน log ของ container เป็น `GUI password: ...` หาได้ที่แท็บ **Logs** ของ pod บน Runpod หรือใน log ของ instance บน Vast.ai รหัสผ่านจะเปลี่ยนเมื่อ container รีสตาร์ท |
| `SD_SCRIPTS_GUI_PASSWORD` | ค่านั้นคือรหัสผ่าน ใช้เมื่ออยากได้รหัสผ่านเดิมทุกครั้งที่รีสตาร์ท |
| `SD_SCRIPTS_GUI_ALLOW_NO_AUTH=1` | ไม่มีรหัสผ่าน ใช้เฉพาะเมื่ออยู่หลัง proxy ของคุณเองที่ยืนยันตัวตนผู้ใช้อยู่แล้ว |

เมื่อเปิดรหัสผ่านอยู่ GUI จะเปิดที่หน้าเข้าสู่ระบบ ให้ใส่รหัสผ่านตามตารางในช่อง **รหัสผ่าน** แล้วกด **เข้าสู่ระบบ** ไม่มีชื่อผู้ใช้ การเข้าสู่ระบบหนึ่งครั้งอยู่ได้ 7 วัน กด **ออกจากระบบ** ในหน้า **ตั้งค่า** เพื่อจบก่อนได้ การรีสตาร์ท container จะทำให้ทุกคนออกจากระบบ ถ้าใส่รหัสผ่านผิดติดกันหลายครั้ง เซิร์ฟเวอร์จะให้รอ นานสุดหนึ่งนาที ก่อนลองครั้งถัดไป หน้า **ตั้งค่า** จะแสดง **การป้องกันด้วยรหัสผ่าน: เปิด** เมื่อใช้งานอยู่

สคริปต์และโปรแกรมอื่นไม่ใช้หน้าเข้าสู่ระบบ แต่ส่งรหัสผ่านไปกับทุก request เป็น `Authorization: Bearer <password>` เช่น `curl -H "Authorization: Bearer <password>" https://<POD_ID>-8000.proxy.runpod.net/api/system/status`

การเข้าสู่ระบบ**ไม่ได้เข้ารหัส**บน address แบบ `http://` ธรรมดา เช่น port ของ Vast.ai ทั้งรหัสผ่านและคุกกี้ของการเข้าสู่ระบบวิ่งเป็นข้อความธรรมดา ใครที่อ่านทราฟฟิกได้ก็นำไปใช้ซ้ำได้ ควรใช้ address แบบ HTTPS เช่น URL proxy ของ Runpod ทุกครั้งที่ทำได้ template ต้องไม่ใส่รหัสผ่านตั้งต้นที่ตายตัวมาให้

## โมเดลความปลอดภัย

- **การล็อกอินเข้า GUI เท่ากับควบคุมเครื่องได้เต็มที่** เหมือนการล็อกอินเข้า Jupyter: สั่งรันคำสั่งเทรน อ่านและเขียนไฟล์ใน workspace และดาวน์โหลดโมเดลได้ ให้ดูแลรหัสผ่านเหมือนรหัสผ่านของเซิร์ฟเวอร์
- **ไฟล์โมเดลอาจมีโค้ดซ่อนอยู่** โหลดโมเดลจากแหล่งที่คุณไว้ใจเท่านั้น
- **path ที่เขียนไฟล์ถูกจำกัดอยู่ใน workspace** โฟลเดอร์ผลลัพธ์ log และ cache ชี้ออกนอกไม่ได้ ข้อนี้กันความผิดพลาด ไม่ใช่ sandbox
- **นำเข้าเฉพาะ training config ที่ไว้ใจได้** config ตั้งตัวเลือกที่มีผลข้างเคียงได้ เช่น `resume_from_huggingface` จะดาวน์โหลดและโหลด training state
- **request ข้ามเว็บไซต์ไปยัง API ถูกบล็อก** เว็บอื่นที่เปิดอยู่ในเบราว์เซอร์จึงสั่ง GUI ไม่ได้

## การใช้งาน GUI

เมื่อเข้าได้แล้ว แอปทำงานเหมือนเวอร์ชันเดสก์ท็อป ทำตาม[เริ่มต้นใช้งาน](quick-start.md) ข้อสังเกตสำหรับ cloud

- อัปโหลดภาพที่ **ชุดข้อมูล (Datasets) > โฟลเดอร์ภาพ** ไฟล์จะอัปโหลดทีละไฟล์ ทำให้แต่ละ request มีขนาดเล็กพอสำหรับ HTTP proxy ของ Runpod และ Vast.ai
- ดาวน์โหลดโมเดลด้วยหน้า[ดาวน์โหลด](downloads.md) จะดึงจาก Hugging Face เข้า pod โดยตรง เร็วกว่าอัปโหลดจากเครื่องของคุณ
- Hugging Face token ที่พิมพ์ในหน้า **ตั้งค่า** เก็บไว้ในหน่วยความจำเท่านั้น จึงหายไปเมื่อ pod รีสตาร์ท ถ้าอยากให้มีทุกครั้งที่เริ่ม ให้ใช้ตัวแปร `HF_TOKEN`

## MCP สำหรับ AI agent

GUI ให้บริการ endpoint [MCP](mcp.md) ด้วย AI agent (Claude Code, Claude Desktop, Cursor) จึงควบคุมแอปได้ ทั้งดาวน์โหลดโมเดล เตรียม dataset ใส่งานเข้าคิว และอ่าน log เปิดอยู่เป็นค่าเริ่มต้นและใช้รหัสผ่านเดียวกับ GUI

| ที่ไหน | MCP URL |
|---|---|
| Runpod | `https://<POD_ID>-8000.proxy.runpod.net/api/mcp` (แสดงใน log ของ container เป็น `Runpod MCP`) |
| Vast.ai | `http://<PUBLIC_IP>:<MAPPED_PORT>/api/mcp` หรือผ่าน SSH tunnel: `ssh -p <SSH_PORT> root@<IP> -L 8000:localhost:8000` แล้วใช้ `http://localhost:8000/api/mcp` |

agent ส่งรหัสผ่านเป็น `Authorization: Bearer <password>` เช่น `claude mcp add --transport http sd-scripts-gui <URL> --header "Authorization: Bearer <password>"` ใครที่มีรหัสนี้ก็ควบคุม pod ได้ และบน address `http://` ธรรมดาของ Vast.ai รหัสเดินทางเป็นข้อความที่อ่านออกได้ จึงควรใช้ SSH tunnel ตั้ง `SD_SCRIPTS_GUI_MCP=0` เพื่อปิด endpoint วิธีตั้งค่าแต่ละ client รายการ tool และการแก้ปัญหาอยู่ใน [MCP สำหรับ AI agent](mcp.md)

## JupyterLab (ตัวสำรองสำหรับผู้ใช้ขั้นสูง)

JupyterLab ทำงานที่ port `8888` โดยมี `/workspace` เป็นโฟลเดอร์ราก ใช้เปิดดูหรือย้ายไฟล์ หรือรัน sd-scripts เองเมื่ออยากทำสิ่งที่ GUI ไม่มี

| รายการ | ค่า |
|---|---|
| Token | ค่าของ `JUPYTER_PASSWORD` ส่งให้ Jupyter ผ่าน environment (ไม่โผล่ใน `ps`) ถ้าไม่ตั้ง ให้หา `token=` ใน log ของ container |
| Kernel | **sd-scripts (Python 3.12)** ซึ่งเป็น environment เดียวกับที่ใช้เทรน |
| Python ใน terminal | `/opt/sd-venv/bin/python` |
| sd-scripts | `/opt/sd-scripts` |

ตัวอย่างใน terminal ของ Jupyter

```bash
cd /workspace
/opt/sd-venv/bin/python -m accelerate.commands.launch /opt/sd-scripts/train_network.py --help
```

ถ้าไม่ต้องใช้ ตั้ง `ENABLE_JUPYTER=0`

## เก็บงานของคุณให้ถาวร

ทุกอย่างที่สำคัญอยู่ใต้ `/workspace` ดังนั้นให้เก็บโฟลเดอร์นั้นไว้บน volume ถาวร

| Path | เนื้อหา |
|---|---|
| `/workspace/models`, `datasets`, `outputs`, `logs` | [workspace](index.md#ไฟล์อยู่ที่ไหน) |
| `/workspace/.sd-scripts-gui` | ประวัติงาน, dataset config และ log ของแต่ละงาน |
| `/workspace/.cache/huggingface` | cache ของ Hugging Face |

ส่วนที่เหลือของดิสก์ใน container (environment ใน `/opt`) จะถูกสร้างใหม่จาก image ทุกครั้งที่เริ่ม การอัปเดตแอปทำได้โดยเริ่ม pod จาก image tag ที่ใหม่กว่าและใช้ volume เดิม
