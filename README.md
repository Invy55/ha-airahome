<div align="center">
  <img src="https://brands.home-assistant.io/airahome/icon.png" height="50px" alt="logo">
</div>

<h3 align="center">Ha-AiraHome</h3>

<div align="center">

  ![Status](https://img.shields.io/badge/status-active-success)
  ![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5)
  ![HACS](https://img.shields.io/badge/HACS-Custom-blue)
  ![Privacy](https://img.shields.io/badge/data-local_only-important)
  [![GitHub Issues](https://img.shields.io/github/issues/invy55/pyairahome)](https://github.com/invy55/pyairahome/issues)
  [![GitHub Pull Requests](https://img.shields.io/github/issues-pr/invy55/pyairahome)](https://github.com/invy55/pyairahome/pulls)
  ![GitHub License](https://img.shields.io/github/license/invy55/pyairahome)
</div>

---

<p align="center"> A custom integration for Home Assistant to connect locally to Aira Heat Pumps via Bluetooth Low Energy (BLE).
    <br> 
</p>

## 📝 Table of Contents
- [About](#about)
- [Getting Started](#getting_started)
- [Usage](#usage)
- [TODO](#todo)
- [Disclaimer](#disclaimer)

## 🧐 About <a name = "about"></a>
**Ha-AiraHome** is a custom integration for [Home Assistant](https://www.home-assistant.io/) that allows local connection to Aira Home heat pumps using **Bluetooth Low Energy (BLE)**. This integration leverages the [PyAiraHome](https://github.com/invy55/pyairahome) library to integrate most available sensors and data points from the device into Home Assistant, providing real-time monitoring. 

## 🏁 Getting Started <a name = "getting_started"></a>

### 🔵 Installation via HACS (Custom Repository)

1. Open HACS → **Integrations**

2. Click on `⋮` (top right menu) → **Custom Repositories**

3. Enter the repository URL:

   ```
   https://github.com/Invy55/Ha-AiraHome
   ```

   Type: **Integration**

4. Confirm → The integration is now in HACS 

5. Find the integration in HACS → Click **Install**

6. Restart Home Assistant

   ```
   Settings → System → Restart
   ```

7. Add the integration:

   ```
   Settings → Devices & Services → ＋Add Integration → AiraHome
   ```

8. Follow the setup instructions in the UI

### 🔵 Installation Manually

1. Download the integration from GitHub Releases:

   [➡️ Ha-AiraHome Releases](https://github.com/Invy55/Ha-AiraHome/releases)

2. Copy the downloaded `airahome` folder to:

   ```
   /config/custom_components/airahome
   ```

3. Restart Home Assistant

   ```
   Settings → System → Restart
   ```

4. Add the integration:

   ```
   Settings → Devices & Services → ＋Add Integration → AiraHome
   ```

5. Follow the setup instructions in the UI

## 📋 Todo(s) <a name = "todo"></a>

- [ ] Implement HA control features (set temperature, mode, etc.)
- [ ] Add support for more sensors and data points

Suggestions and contributions are welcome! Feel free to open an issue or pull request with your ideas.


## ⚠️ Disclaimer <a name = "disclaimer"></a>

**PyAiraHome** is an independent, open-source software library developed for interacting with Aira Home heat pumps via their app gRPC APIs and Bluetooth Low Energy protocols. This project is **not affiliated with, endorsed by, sponsored by, or associated with** Aira Home or any of its subsidiaries, affiliates, or partners.

### Important Legal Notice

- 🔒 This project is **not an official product** of Aira Home
- ⚖️ Use of this integration does **not imply any compatibility, support, or approval** from Aira Home
- 🏷️ All trademarks, service marks, and company names mentioned herein are the **property of their respective owners**
- ⚠️ **Use of this integration is at your own risk** - I'm not responsible for any damages, malfunctions, warranty voids, or issues arising from its use
- 🛡️ This software is provided **"AS IS"** without warranty of any kind, express or implied
- 🔍 No proprietary code, trade secrets, or copyrighted materials from Aira Home have been used in the development of this integration.

**By using this integration, you acknowledge that you understand and accept these terms and any associated risks.**