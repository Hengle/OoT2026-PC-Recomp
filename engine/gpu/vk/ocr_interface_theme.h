// Shared interface colors. The integer blends match launcher/interface_theme.py.
#pragma once
#include <algorithm>
#include <cmath>
namespace mkwvk {
inline int ocr_ui_r = 46, ocr_ui_g = 123, ocr_ui_b = 255;
inline int ocr_ui_preset = 0;
namespace interface_theme {
struct RGB { int r, g, b; };
inline RGB mix(RGB a, RGB b, int p) {
    return {(a.r*(100-p)+b.r*p+50)/100, (a.g*(100-p)+b.g*p+50)/100, (a.b*(100-p)+b.b*p+50)/100};
}
inline double linear(int c) {
    double v = c / 255.0;
    return v <= .04045 ? v / 12.92 : std::pow((v+.055)/1.055, 2.4);
}
inline double luminance(RGB c) { return .2126*linear(c.r) + .7152*linear(c.g) + .0722*linear(c.b); }
inline RGB foreground(RGB c) { return luminance(c) > .179 ? RGB{0,0,0} : RGB{255,255,255}; }
inline RGB tint(RGB base, RGB color) {
    int span = std::max({base.r,base.g,base.b}) - std::min({base.r,base.g,base.b});
    auto channel = [span](int b,int a,int d) {
        return std::clamp(b + (int)std::floor(((a-d)*span+104)/209.0),0,255);
    };
    return {channel(base.r,color.r,46),channel(base.g,color.g,123),channel(base.b,color.b,255)};
}
inline RGB button_foreground(RGB color) {
    return luminance(tint({59,139,255},color)) <= .30 ? RGB{255,255,255} : RGB{0,0,0};
}
inline constexpr RGB presets[] = {{46,123,255}, {0,184,176}, {66,184,108}, {168,121,238},
                                  {237,118,174}, {232,173,69}, {189,200,218}};
inline void select_preset(int n) {
    if (n < 0 || n >= 7) return;
    ocr_ui_r = presets[n].r; ocr_ui_g = presets[n].g; ocr_ui_b = presets[n].b;
}
inline int preset_index() {
    for (int i=0; i<7; ++i)
        if (ocr_ui_r == presets[i].r && ocr_ui_g == presets[i].g && ocr_ui_b == presets[i].b) return i;
    return 7;
}
} // namespace interface_theme
} // namespace mkwvk
