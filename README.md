<div align="center">
  <img src="https://brands.home-assistant.io/airahome/icon.png" height="50px" alt="logo">
</div>

<h3 align="center">Ha-AiraHome</h3>

<div align="center">

  ![Status](https://img.shields.io/badge/status-active-success)
  ![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5)
  ![HACS](https://img.shields.io/badge/HACS-Custom-blue)
  ![Privacy](https://img.shields.io/badge/data-local_only-important)
  [![GitHub Issues](https://img.shields.io/github/issues/invy55/ha-airahome)](https://github.com/invy55/ha-airahome/issues)
  [![GitHub Pull Requests](https://img.shields.io/github/issues-pr/invy55/ha-airahome)](https://github.com/invy55/ha-airahome/pulls)
  ![GitHub License](https://img.shields.io/github/license/invy55/ha-airahome)
</div>

---

<p align="center"> A custom integration for Home Assistant to connect locally to Aira Heat Pumps via Bluetooth Low Energy (BLE).
    <br> 
</p>

## 📝 Table of Contents
- [About](#about)
- [Getting Started](#getting_started)
- [TODO](#todo)
- [Disclaimer](#disclaimer)

## 🧐 About <a name = "about"></a>
**Ha-AiraHome** is a custom integration for [Home Assistant](https://www.home-assistant.io/) that allows local connection to Aira Home heat pumps using **Bluetooth Low Energy (BLE)**. This integration leverages the [PyAiraHome](https://github.com/invy55/pyairahome) library to integrate most available sensors and data points from the device into Home Assistant, providing real-time monitoring. 

## 🏁 Getting Started <a name = "getting_started"></a>

### 🔵 Installation via HACS (Custom Repository)
**METHOD 1:**

Click on the button below to install it directly:

[![hacs](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=invy55&repository=ha-airahome&category=integration)

Done! Now simply add an integration, you can do that from ha or by clicking here:

[![hacs](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=airahome)

For more installation methods check [the wiki here](https://github.com/Invy55/ha-airahome/wiki/Installation)!

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
