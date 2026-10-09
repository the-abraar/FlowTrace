# RSSI Calibration & Positioning Deep Dive

## The Math: Log-Distance Path Loss Model

RSSI (Received Signal Strength Indicator) decays logarithmically with distance.

Formula: `d = 10 ^ ((TxPower - RSSI) / (10 * n))`

Where:
*   `TxPower`: The RSSI value measured at exactly 1 meter from the transmitter.
*   `n`: The path loss exponent (environmental factor).

## Environmental Factors (`n` values)
*   **2.0**: Free space (perfect vacuum, theoretical).
*   **2.2 - 2.5**: Office environment (drywall, desks).
*   **3.0 - 3.5**: Crowded venue (human bodies absorb 2.4GHz BLE signals heavily).
*   **4.0+**: Obstructed path (concrete walls).

## Calibration Procedure

1.  **Determine TxPower:**
    *   Place a scanner node.
    *   Place a beacon exactly 1.0 meter away, at the same height.
    *   Record 100 RSSI samples and take the median.
    *   This is your `TxPower` (typically around -59 dBm to -65 dBm).

2.  **Determine `n`:**
    *   Move the beacon to exactly 3.0 meters away.
    *   Measure median RSSI.
    *   Use the formula: `n = (TxPower - RSSI) / (10 * log10(3))`
    *   Adjust `n` in `backend/config.py` based on the venue type.

## Triangulation and Smoothing

*   **Weighted Least Squares (WLS):** We use WLS because closer readings (higher RSSI) are significantly more accurate than distant readings.
*   **Kalman Filter:** Raw RSSI is incredibly noisy (can bounce +/- 10 dBm standing still). The backend uses a 2D Kalman filter to smooth the position trajectory, assuming a constant velocity model.
