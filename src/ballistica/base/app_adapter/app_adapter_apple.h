// Released under the MIT License. See LICENSE for details.

#ifndef BALLISTICA_BASE_APP_ADAPTER_APP_ADAPTER_APPLE_H_
#define BALLISTICA_BASE_APP_ADAPTER_APP_ADAPTER_APPLE_H_

#if BA_XCODE_BUILD

#include <mutex>
#include <thread>
#include <vector>

#include "ballistica/base/app_adapter/app_adapter.h"
#include "ballistica/shared/generic/runnable.h"
#include "ballistica/shared/math/vector2f.h"

namespace ballistica::base {

class AppAdapterApple : public AppAdapter {
 public:
  /// Given base, returns app-adapter cast to our type. This assumes it
  /// actually *is* our type.
  static auto Get(BaseFeatureSet* base) -> AppAdapterApple* {
    auto* val = static_cast<AppAdapterApple*>(base->app_adapter);
    assert(val);
    assert(dynamic_cast<AppAdapterApple*>(base->app_adapter) == val);
    return val;
  }

  auto ManagesMainThreadEventLoop() const -> bool override;
  void DoApplyAppConfig() override;

  /// Called by FromSwift.
  auto TryRender() -> bool;

  /// Called by FromSwift.
  // void SetScreenResolution(float pixel_width, float pixel_height);

  auto FullscreenControlAvailable() const -> bool override;
  auto FullscreenControlGet() const -> bool override;
  void FullscreenControlSet(bool fullscreen) override;
  auto FullscreenControlKeyShortcut() const
      -> std::optional<std::string> override;

  auto HasDirectKeyboardInput() -> bool override;

  void EnableResizeFriendlyMode(int width, int height);

 protected:
  void DoPushMainThreadRunnable(Runnable* runnable) override;
  void DoPushGraphicsContextRunnable(Runnable* runnable) override;
  auto InGraphicsContext() -> bool override;
  auto ShouldUseCursor() -> bool override;
  auto HasHardwareCursor() -> bool override;
  void SetHardwareCursorVisible(bool visible) override;
  void TerminateApp() override;
  void ApplyGraphicsSettings(const GraphicsSettings* settings) override;

 private:
  class ScopedAllowGraphics_;

  void UpdateScreenSizes_();
  void ReloadRenderer_(const GraphicsSettings* settings);

  std::thread::id graphics_thread_{};
  bool graphics_allowed_ : 1 {};
  uint8_t resize_friendly_frames_{};
  Vector2f resize_target_resolution_{-1.0f, -1.0f};
  std::mutex graphics_calls_mutex_;
  std::vector<Runnable*> graphics_calls_;
};

}  // namespace ballistica::base

#endif  // BA_XCODE_BUILD

#endif  // BALLISTICA_BASE_APP_ADAPTER_APP_ADAPTER_APPLE_H_
