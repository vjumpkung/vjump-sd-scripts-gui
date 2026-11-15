# MCP: ให้ AI agent ควบคุม GUI

[English](../en/mcp.md) | [ภาษาไทย](mcp.md)

## 1. คืออะไร

SD-Scripts GUI มี [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server ในตัว ทำให้ AI agent เช่น Claude Code, Claude Desktop หรือ Cursor ทำได้ทุกอย่างที่คุณทำได้ในหน้าเว็บ ไม่ว่าจะดาวน์โหลดโมเดล อัปโหลดและใส่ caption ให้ภาพ สร้าง dataset config เลือก preset สำหรับเทรน ใส่งานเข้าคิว ดู log และเก็บไฟล์ผลลัพธ์

- เป็นส่วนหนึ่งของแอป ไม่ต้องรันโปรแกรม เปิด port หรือเข้าสู่ระบบเพิ่ม
- **เปิดอยู่เป็นค่าเริ่มต้น** และอยู่ที่ `/api/mcp` บน address เดียวกับ GUI
- มี tool 41 ตัว แต่ละตัวทำงานเหมือนหน้าที่ตรงกันใน GUI ทุกอย่าง ทั้งการตรวจสอบและข้อจำกัด agent ได้คำตอบแบบกระชับและคู่มือขั้นตอนสั้น ๆ จึงเรียกน้อยครั้ง
- ใช้ HTTP ธรรมดา (transport แบบ "Streamable HTTP" ของ MCP) client ที่รู้จักแค่การเปิดโปรแกรมในเครื่องใช้ bridge ตัวเล็กได้ ดู [Claude Desktop](#claude-desktop)

## 2. URL

address คือ address ของ GUI ต่อด้วย `/api/mcp` ใช้ URL ตรงตัวนี้ โดยไม่มี slash ปิดท้าย ถ้ามี slash (`/api/mcp/`) server จะตอบ `307` redirect ไปยัง address ที่ถูกต้อง (หรือตอบ `401` ก่อนถ้าตั้งรหัสผ่านไว้แต่ไม่มี header) และ client บางตัวไม่ตาม redirect ของ `POST` หรืออาจทิ้ง header `Authorization` เมื่อ redirect ผ่าน HTTPS proxy

| วิธีที่รันแอป | MCP URL |
|---|---|
| `run-browser.bat` (แนะนำบน Windows) | `http://127.0.0.1:8000/api/mcp` port คือ `8000` ถ้าไม่ได้ตั้ง `SD_SCRIPTS_GUI_PORT` หน้าต่าง console จะแสดง URL ให้ |
| `run.bat` (หน้าต่างเดสก์ท็อป) | `http://127.0.0.1:17860/api/mcp` แต่ใช้ได้เฉพาะตอนที่หน้าต่างเปิดอยู่ ถ้า port `17860` ถูกใช้อยู่ แอปจะสุ่ม port ที่ว่าง: ดูบรรทัด `MCP endpoint (while this window is open): ...` ใน console |
| Docker บนเครื่องของคุณ | `http://localhost:8000/api/mcp` |
| Runpod | `https://<POD_ID>-8000.proxy.runpod.net/api/mcp` (log ของ container แสดงเป็น `Runpod MCP`) |
| Vast.ai | `http://<PUBLIC_IP>:<MAPPED_PORT>/api/mcp` โดยใช้ address และ port ภายนอกที่ map กับ port `8000` ของ container ที่ปลอดภัยกว่าคือ SSH tunnel ดูด้านล่าง |

`run-browser.bat` เป็นตัวเลือกในเครื่องที่ง่ายที่สุด เพราะ port คงที่และทำงานต่อไปตราบเท่าที่หน้าต่าง console ยังเปิดอยู่ ส่วนหน้าต่างเดสก์ท็อปจะปิด server ไปพร้อมกับหน้าต่าง

บน Windows แอปตอบเฉพาะ `127.0.0.1` และ `localhost` ให้ใช้ชื่อใดชื่อหนึ่งนี้ ไม่ใช่ address ในวง LAN

**Vast.ai ผ่าน SSH tunnel** port ของ Vast.ai เป็น `http://` ธรรมดาบน address สาธารณะ เพื่อไม่ให้รหัสผ่านเดินทางบนอินเทอร์เน็ตแบบเปิด ให้ forward port ผ่าน SSH แล้วใช้ `localhost`

```bash
ssh -p <SSH_PORT> root@<IP> -L 8000:localhost:8000
```

เปิด terminal นั้นทิ้งไว้ แล้วใช้ `http://localhost:8000/api/mcp` พอร์ต SSH และ IP อยู่ในแผงของ instance บน Vast.ai (ปุ่ม **Connect**)

## 3. การยืนยันตัวตน

| ที่ไหน | รหัสผ่าน |
|---|---|
| Windows (`run.bat`, `run-browser.bat`) | ไม่มีเป็นค่าเริ่มต้น ตั้ง `SD_SCRIPTS_GUI_PASSWORD` ก่อนเริ่มถ้าต้องการ |
| Docker, Runpod, Vast.ai | มี container สร้างรหัสผ่านสุ่มทุกครั้งที่เริ่มและแสดงใน log เป็น `GUI password: ...` ตั้ง `SD_SCRIPTS_GUI_PASSWORD` เพื่อใช้รหัสผ่านของคุณเองและคงไว้หลังรีสตาร์ท ดู [Cloud: Runpod และ Vast.ai](cloud-runpod-vast.md#รหัสผ่าน) |

เมื่อมีรหัสผ่าน client ต้องส่งรหัสผ่านใน header ทุก request

```
Authorization: Bearer <password>
```

agent ไม่มีหน้าเข้าสู่ระบบและไม่มี OAuth client ที่ส่ง header เองไม่ได้ หรือเข้าสู่ระบบได้แค่ด้วย OAuth จะเชื่อมต่อ server ที่มีรหัสผ่านไม่ได้ ถ้าไม่มี header server จะตอบ `401`

**รหัสผ่านผิดทำให้ทุกคนถูกล็อกชั่วคราว** server นับรหัสผ่านที่ผิดด้วยตัวนับเดียวทั้งระบบ ซึ่งหน้าเข้าสู่ระบบและ client แบบ Bearer หรือ Basic ทุกตัวใช้ร่วมกัน เมื่อใส่ผิดติดกัน 5 ครั้ง การตรวจรหัสผ่านทุกครั้งจะถูกปฏิเสธด้วย `429` นานได้ถึงหนึ่งนาที และการล็อกจะนานขึ้นตามจำนวนครั้งที่ผิดต่อ ๆ ไป ดังนั้น client ที่ลองส่งรหัสผ่านเก่าซ้ำ ๆ จะทำให้คนอื่นเข้าสู่ระบบใหม่ไม่ได้ด้วย กรณีที่พบบ่อยคือรีสตาร์ท Docker แล้วได้รหัสผ่านสุ่มใหม่: หลังรีสตาร์ทให้แก้ header ใน client และหยุด client ที่ยังส่งรหัสเก่า เซสชันเบราว์เซอร์ที่เข้าสู่ระบบอยู่แล้วไม่ได้รับผลกระทบ

## 4. เชื่อมต่อ client

แทน `<URL>` ด้วย address จากตารางด้านบน และ `<password>` ด้วยรหัสผ่านของคุณ ถ้าไม่มีรหัสผ่านให้ข้าม header

### Claude Code

```bash
# ในเครื่อง ไม่มีรหัสผ่าน
claude mcp add --transport http sd-scripts-gui http://127.0.0.1:8000/api/mcp

# มีรหัสผ่าน
claude mcp add --transport http sd-scripts-gui <URL> --header "Authorization: Bearer <password>"
```

ถ้าอยากแชร์การตั้งค่าในโปรเจกต์โดยไม่เขียนรหัสผ่านลงไฟล์ ให้สร้าง `.mcp.json` ในโปรเจกต์แล้วอ่านรหัสผ่านจาก environment variable

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "type": "http",
      "url": "https://<POD_ID>-8000.proxy.runpod.net/api/mcp",
      "headers": {
        "Authorization": "Bearer ${SD_GUI_PASSWORD}"
      }
    }
  }
}
```

ตั้ง `SD_GUI_PASSWORD` ใน shell ที่ใช้เปิด Claude Code แล้วพิมพ์ `/mcp` ใน Claude Code เพื่อตรวจว่า `sd-scripts-gui` เชื่อมต่อแล้ว

### Claude Desktop

Claude Desktop เปิดได้เฉพาะโปรแกรมในเครื่อง จึงต้องเข้าถึง server ผ่าน bridge ตัวเล็ก [`fastmcp-remote`](https://pypi.org/project/fastmcp-remote/) ที่เปิดด้วย `uvx` (`install.bat` ติดตั้ง uv ให้แล้ว ถ้ายังไม่มีให้ติดตั้ง [uv](https://docs.astral.sh/uv/)) เปิด **Settings > Developer > Edit Config** แล้วเพิ่มใน `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "command": "uvx",
      "args": [
        "fastmcp-remote",
        "https://<POD_ID>-8000.proxy.runpod.net/api/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer <password>"
      }
    }
  }
}
```

สำหรับ server ในเครื่องที่ไม่มีรหัสผ่าน ต้องบอก bridge ไม่ให้เริ่มการเข้าสู่ระบบแบบ OAuth

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "command": "uvx",
      "args": ["fastmcp-remote", "http://127.0.0.1:8000/api/mcp", "--auth", "none"]
    }
  }
}
```

รีสตาร์ท Claude Desktop หลังแก้ ถ้าชอบ Node.js ใช้ `npx mcp-remote <URL> --header "Authorization:${AUTH_HEADER}"` ได้แบบเดียวกัน

### Cursor และ client อื่น

client ใดก็ได้ที่รองรับ remote MCP server พร้อม custom header ใช้ได้ ใน Cursor ใส่ค่านี้ใน `~/.cursor/mcp.json` (หรือ `.cursor/mcp.json` ในโปรเจกต์)

```json
{
  "mcpServers": {
    "sd-scripts-gui": {
      "url": "https://<POD_ID>-8000.proxy.runpod.net/api/mcp",
      "headers": {
        "Authorization": "Bearer <password>"
      }
    }
  }
}
```

การตั้งค่าเป็นสามอย่างเดิมเสมอ คือ URL, transport แบบ "Streamable HTTP" (client ส่วนใหญ่เรียกว่า `http`) และ header `Authorization`

## 5. Tool ทั้งหมด

tool ทั้ง 41 ตัว agent ยังได้รับคู่มือขั้นตอนเมื่อเชื่อมต่อ คุณจึงไม่ต้องอธิบายลำดับการทำงานเอง

**ระบบ, preset และไฟล์**

| Tool | ทำอะไร |
|---|---|
| `get_overview` | เริ่มที่นี่: sd-scripts พร้อมหรือไม่, สถานะคิว, งานที่กำลังรัน, งานในคิว, การดาวน์โหลดที่กำลังทำ, secret ที่ตั้งไว้, GPU และ RAM |
| `rescan_schema` | สร้าง argument schema ของ sd-scripts ใหม่หลังเปลี่ยน checkout |
| `set_secrets` | ตั้งหรือล้าง Hugging Face token และ W&B key (เก็บในหน่วยความจำ ไม่แสดงกลับ) |
| `list_presets` | รายการ preset สำหรับเทรนแบบย่อ เลือกเฉพาะตระกูลโมเดลได้ |
| `get_preset` | preset หนึ่งตัว: ค่าเริ่มต้น, พารามิเตอร์หลักพร้อมคำอธิบาย, ไฟล์โมเดลและสถานะการดาวน์โหลด, request template และค่าที่ยังต้องเลือกเอง |
| `search_script_args` | ค้นหา argument ทั้งหมดของสคริปต์ด้วยคำ ชื่อเต็ม หรือกลุ่ม ถ้าไม่ใส่ตัวกรองจะสรุปเป็นกลุ่ม |
| `browse_workspace` | แสดงโฟลเดอร์ใน workspace (models, datasets, outputs, logs) |

**Dataset และโฟลเดอร์ภาพ**

| Tool | ทำอะไร |
|---|---|
| `list_datasets` | dataset config ที่บันทึกไว้ |
| `get_dataset` | dataset config หนึ่งตัวพร้อมเนื้อหาเต็ม |
| `validate_dataset` | ตรวจว่าโฟลเดอร์มีอยู่ และนับภาพกับ caption |
| `export_dataset_toml` | dataset config เป็นข้อความ TOML ของ sd-scripts |
| `create_dataset` | สร้าง dataset config |
| `update_dataset` | แทนที่ dataset config ทั้งหมด |
| `delete_dataset` | ลบ dataset config (ภาพและงานเก่าไม่ถูกแตะ) |
| `import_dataset_toml` | สร้าง dataset config จากข้อความ TOML |
| `list_image_folders` | โฟลเดอร์ภาพพร้อมจำนวนภาพและ caption |
| `create_image_folder` | สร้างโฟลเดอร์ภาพเปล่า |
| `list_folder_images` | ภาพในโฟลเดอร์พร้อม caption ทีละหน้า เลือกเฉพาะภาพที่ยังไม่มี caption ได้ |
| `set_captions` | เขียนไฟล์ caption ให้หลายภาพพร้อมกัน |
| `upload_image` | อัปโหลดภาพหนึ่งภาพเป็น base64 (ไม่เกินประมาณ 3 MB) พร้อม caption ถ้าต้องการ |
| `view_image` | ดูภาพหนึ่งภาพ (ไม่เกิน 2 MiB) |
| `delete_images` | ลบภาพและ caption ของภาพ |
| `delete_image_folder` | ลบทั้งโฟลเดอร์ภาพ |

**ดาวน์โหลดโมเดล**

| Tool | ทำอะไร |
|---|---|
| `list_download_catalog` | ชุดโมเดล ขนาด และไฟล์ที่มีอยู่แล้ว |
| `start_model_download` | ดาวน์โหลดชุดโมเดลจาก Hugging Face ในเบื้องหลัง |
| `list_downloads` | การดาวน์โหลดตั้งแต่ server เริ่มทำงาน |
| `get_download` | ความคืบหน้าของการดาวน์โหลด รอจนเสร็จได้ (สูงสุด 55 วินาทีต่อครั้ง) |
| `cancel_download` | ยกเลิกการดาวน์โหลดที่กำลังทำ |

**การเทรนและคิว**

| Tool | ทำอะไร |
|---|---|
| `preview_training` | ตรวจ request และแสดงคำสั่งกับ dataset TOML ที่จะใช้ ไม่เขียนอะไร |
| `submit_training_job` | ใส่งานเข้าคิว (คิวยังหยุดอยู่) |
| `list_jobs` | งานเรียงจากใหม่ไปเก่า กรองตามสถานะได้ |
| `get_job` | งานหนึ่งตัวพร้อมความคืบหน้าและข้อผิดพลาด |
| `wait_for_job` | รอให้สถานะของงานเปลี่ยน (สูงสุด 55 วินาทีต่อครั้ง) |
| `get_job_logs` | ส่วนท้ายของ log ที่ทำความสะอาดแล้ว หรือบรรทัดใหม่ตั้งแต่ offset ที่ระบุ |
| `list_job_artifacts` | ไฟล์ checkpoint ที่งานสร้าง พร้อมลิงก์ดาวน์โหลด |
| `get_job_config` | request ที่ใช้ส่งงาน เพื่อทำซ้ำหรือปรับแก้ |
| `cancel_job` | ยกเลิกงานที่รออยู่หรือกำลังรัน |
| `retry_job` | ใส่สำเนาของงานที่ล้มเหลวหรือถูกยกเลิกเข้าคิว |
| `move_job` | เปลี่ยนตำแหน่งของงานที่รออยู่ |
| `delete_job` | ลบข้อมูลและ log ของงานที่จบแล้ว (ไม่ลบ checkpoint) |
| `set_queue_state` | เริ่มหรือหยุดคิว การเริ่มแต่ละครั้งรันงานเพียงหนึ่งงาน |

เรื่องที่ agent รู้จากคู่มือขั้นตอน และควรรู้ด้วยตัวคุณเอง

- คิวเริ่ม**หยุดอยู่** และหยุดอีกครั้งหลังจบทุกงานและทุกครั้งที่ส่งงานเข้าคิว agent ต้องเรียก `set_queue_state` ด้วย `running` สำหรับแต่ละงาน เหมือนกดปุ่ม **เริ่ม** ใน GUI
- `values` ใน request ของการเทรนใช้ชื่อ argument ของ sd-scripts เป็น key (เช่น `network_dim`) ค่าเริ่มต้นของ preset ถูกรวมให้ก่อน agent จึงส่งเฉพาะค่าที่ต่างออกไป ส่ง `null` ให้ชื่อใดก็ได้เพื่อตัดค่าเริ่มต้นนั้นทิ้ง
- path เป็น path สัมพัทธ์กับโฟลเดอร์ workspace (เช่น `models/vae/ae.safetensors`)
- รายการมีขีดจำกัดจำนวน และทุกรายการมี `next_offset` สำหรับหน้าถัดไป

## 6. ตัวอย่างการใช้งาน

สั่งด้วยภาษาธรรมดาได้เลย เช่น *"เทรน FLUX LoRA ของแมวฉัน ภาพอยู่ที่ D:\photos\cat ใช้ 10 epoch และตั้งชื่อ cat_flux"* agent ที่ดีจะทำประมาณนี้

1. `get_overview` เพื่อดูว่า sd-scripts พร้อมและคิวว่าง
2. `get_preset` ของ `flux-lora` เห็นว่าไฟล์โมเดลยังไม่มี จึงเรียก `start_model_download` สำหรับ `flux1-dev` แล้วรอด้วย `get_download` โมเดลที่ต้องขอสิทธิ์ต้องมี Hugging Face token ก่อน ผ่าน `set_secrets` หรือ **ตั้งค่า** ใน GUI
3. `create_image_folder` แล้วคัดลอกภาพไปที่ `workspace/datasets/cat` ถ้า agent รันบนเครื่องเดียวกันก็คัดลอกไฟล์เองได้ ไม่เช่นนั้นใช้ `upload_image` สำหรับไม่กี่ภาพ หรือ `curl` ไปที่ `PUT /api/datasets/folders/cat/files` เมื่อมีหลายภาพ แล้วเขียน caption ด้วย `set_captions` (หรือคุณให้ไฟล์ `.txt` ไป)
4. `create_dataset` ชี้ไปที่ `datasets/cat` แล้ว `validate_dataset` จนได้ `ok`
5. `preview_training` ด้วย preset, dataset และ `{"output_name": "cat_flux", "max_train_epochs": 10}` แล้วแก้ทุกปัญหาที่อยู่ใน `errors`
6. `submit_training_job` แล้ว `set_queue_state` ด้วย `running`
7. `wait_for_job` และ `get_job_logs` เพื่อติดตามการรัน แล้ว `list_job_artifacts` เพื่อรับไฟล์ LoRA และลิงก์ดาวน์โหลด

คุณดูการรันเดียวกันนี้ใน GUI ได้พร้อมกัน งานจะปรากฏในหน้า **งาน** เหมือนงานอื่น

## 7. ความปลอดภัย

- **ใครที่มี address ของ MCP และรหัสผ่านก็ควบคุมเครื่องได้** เหมือนคนที่เข้าสู่ระบบ GUI คือรันคำสั่งเทรน อ่านและเขียนไฟล์ใน workspace และดาวน์โหลดโมเดลได้ ให้ดูแลรหัสผ่านเหมือนรหัสผ่านของ server
- **บน Vast.ai (`http://` ธรรมดา) รหัสผ่านเดินทางเป็นข้อความที่อ่านออกได้** ใครที่ดักข้อมูลบนเส้นทางได้ก็นำไปใช้ซ้ำได้ ควรใช้ SSH tunnel จาก[ส่วน URL](#2-url) หรือ address แบบ HTTPS เช่น proxy ของ Runpod
- **อย่า commit รหัสผ่าน** เก็บไว้ใน environment variable แล้วอ้างจากการตั้งค่า client เหมือนตัวอย่าง `.mcp.json` ด้านบน และอย่าวางลงในแชต
- **รหัสผ่านของ Docker image เปลี่ยนทุกครั้งที่เริ่ม** ถ้าไม่ได้ตั้ง `SD_SCRIPTS_GUI_PASSWORD` หลังรีสตาร์ทให้แก้ header ใน client
- **token ที่ส่งให้ `set_secrets` ผ่านบทสนทนา**กับบริการ AI ใช้ Hugging Face token ที่คุณยอมแชร์กับบริการนั้น หรือตั้ง `HF_TOKEN` เป็น environment variable ของ container แทน
- request ข้ามเว็บไซต์จากเบราว์เซอร์ถูกปฏิเสธ และการตรวจสอบของ GUI (เขียนได้เฉพาะใน workspace, ไม่ใช้ shell, ไม่ส่ง secret กลับ) ใช้กับทุก tool

## 8. ปิดการใช้งาน

ตั้ง environment variable `SD_SCRIPTS_GUI_MCP=0` ก่อนเริ่มแอป address `/api/mcp` จะตอบ `404` บน Windows ตั้งใน console ก่อนรัน `run-browser.bat` หรือใช้ `setx SD_SCRIPTS_GUI_MCP 0` บน Runpod และ Vast.ai เพิ่มใน environment variable ของ template

## 9. แก้ปัญหา

| สิ่งที่เห็น | สาเหตุและวิธีแก้ |
|---|---|
| `401` หรือ "Authentication required" | header ไม่มีหรือไม่ถูกต้อง ส่ง `Authorization: Bearer <password>` รหัสผ่านของ Docker เปลี่ยนทุกครั้งที่เริ่ม: อ่านรหัสใหม่ใน log ของ container |
| `429` "Too many failed login attempts" | ใส่รหัสผ่านผิดติดกันหลายครั้ง ตัวนับนี้ใช้ร่วมกันทั้งระบบ คือหน้าเข้าสู่ระบบและ client แบบ Bearer หรือ Basic ทุกตัว ดังนั้น MCP client ที่ยังส่งรหัสผ่านเก่าอยู่ (เช่นหลังรีสตาร์ท Docker ที่สร้างรหัสใหม่) จะทำให้คนอื่นเข้าสู่ระบบใหม่ไม่ได้ด้วย แก้ header ของ client หลังรีสตาร์ท และตรวจว่าไม่มี client ไหนลองรหัสเก่าซ้ำ รอตามจำนวนวินาทีในข้อความ (สูงสุดหนึ่งนาที) แล้วลองใหม่ เซสชันเบราว์เซอร์ที่เข้าสู่ระบบอยู่แล้วไม่ได้รับผลกระทบ |
| `403` "Cross-site requests are not allowed" | หน้าเว็บในเบราว์เซอร์พยายามเรียก endpoint ให้ใช้ MCP client ไม่ใช่หน้าเว็บ |
| `404` | MCP ถูกปิด (`SD_SCRIPTS_GUI_MCP=0`) หรือ path ผิด URL ต้องลงท้ายด้วย `/api/mcp` |
| `307` redirect หรือ `401` ทันทีหลังเติม slash ท้าย URL | ใช้ URL ตรงตัวที่ไม่มี slash ปิดท้าย: `.../api/mcp` ไม่ใช่ `.../api/mcp/` client ไม่ได้ตาม redirect ทุกตัว และเมื่ออยู่หลัง HTTPS proxy redirect อาจทิ้ง header `Authorization` |
| `400` "Invalid host header" | แอปตอบเฉพาะชื่อใน `SD_SCRIPTS_GUI_ALLOWED_HOSTS` บน Windows ใช้ `127.0.0.1` หรือ `localhost` |
| Connection refused หรือ client เชื่อมต่อไม่ได้ | แอปไม่ได้รันอยู่, port ต่างไป (หน้าต่างเดสก์ท็อปอาจใช้ port สุ่ม: ดู console) หรือ SSH tunnel ถูกปิด |
| `405` เมื่อเปิด address ในเบราว์เซอร์ | ปกติ endpoint รับเฉพาะ `POST` จาก MCP client |
| client รอนานที่ `get_download` หรือ `wait_for_job` | tool สองตัวนี้รอไม่เกิน 55 วินาทีแล้วคืนสถานะปัจจุบัน เรียกซ้ำเพื่อรอต่อ |
| tool แจ้ง `HTTP 503` | environment ของ sd-scripts ไม่มีหรือไม่ครบ `get_overview` บอกว่าขาดอะไร บน Windows รัน `install.bat` อีกครั้ง |
| request "ใหญ่เกินไป" | request MCP หนึ่งครั้งใหญ่ได้ไม่เกิน 4 MiB อัปโหลดภาพใหญ่ด้วย `curl` หรือคัดลอกลงโฟลเดอร์แทนการใช้ `upload_image` |
| agent ลืมเริ่มงาน | คิวหยุดหลังส่งงานทุกครั้ง บอกให้เรียก `set_queue_state` ด้วย `running` |

ปัญหาอื่นของแอปเอง ดู[แก้ปัญหา](troubleshooting.md)
