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
- [Community](#community)
- [Support Me](#supportme)
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
### For pre-release
- [x] Save useful data during set-up by connecting to the unit - [1](https://github.com/Invy55/ha-airahome/commit/9e5cae05ad9e5aaaa14fd1f9033550274e10654d) [2](https://github.com/Invy55/ha-airahome/commit/76b28708c0f734adc82c776817cdcbffc2e58f17)
- [ ] Rewrite zones and phases detections to prevent #1
- [ ] Understand the best procedure for connection issues (stop the integration? prompt the user after a number of checks? let ha handle it?)
- [ ] Rewrite entities with strings/lang(s).json - [1](https://github.com/Invy55/ha-airahome/commit/7f572373c9ff9777b829ea03e35fce92b401ad19)
- [x] Fix BLE autodiscovery and pairing - [1](https://github.com/Invy55/ha-airahome/commit/9e5cae05ad9e5aaaa14fd1f9033550274e10654d)
- [ ] Write an exhaustive [bluetooth issues guide](https://github.com/Invy55/ha-airahome/wiki/Bluetooth-Issues)
- [ ] Implement actions (hot_water_boosting, set_dhw_temperature, ..., refresh_saved_data)
- [ ] Add entities for heat pump version
- [ ] Add thermostats climate entities

### General
- [ ] Add support for more sensors and data points

### Future/Not possible
- [ ] Fix Write Not Permitted - #10
- [ ] Add support for solar plants


Suggestions and contributions are welcome! Feel free to open an issue or pull request with your ideas.

## 🌐 Community <a name = "community"></a>
If you enjoy this project and want to **connect with other users**, we'd love to see you in our community. Come and join us at [airausersforum.com](https://airausersforum.com)!

## ☕ Support me <a name = "supportme"></a>
I created and currently mantain this project because I genuinely enjoy doing so. No need to tip — but if you’d still like to show some appreciation you can do it by clicking on the button below, thank you!

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Y8Y01NUQV3)

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
