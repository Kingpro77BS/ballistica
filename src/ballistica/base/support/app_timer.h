// Released under the MIT License. See LICENSE for details.

#ifndef BALLISTICA_BASE_SUPPORT_APP_TIMER_H_
#define BALLISTICA_BASE_SUPPORT_APP_TIMER_H_

#include "ballistica/base/base.h"
#include "ballistica/base/logic/logic.h"
#include "ballistica/shared/ballistica.h"
#include "ballistica/shared/foundation/object.h"
#include "ballistica/shared/generic/lambda_runnable.h"

namespace ballistica::base {

class AppTimer : public Object {
 public:
  AppTimer(millisecs_t length, bool repeat, Runnable* runnable) {
    assert(g_base->InLogicThread());
    timer_id_ = base::g_base->logic->NewAppTimer(length, repeat, runnable);
  }

  template <typename F>
  static auto New(millisecs_t length, bool repeat, const F& lambda) {
    return Object::New<AppTimer>(length, repeat,
                                 NewLambdaRunnable<F>(lambda).Get());
  }

  void SetLength(millisecs_t length) {
    assert(g_base->InLogicThread());
    base::g_base->logic->SetAppTimerLength(timer_id_, length);
  }
  ~AppTimer() override {
    assert(g_base->InLogicThread());
    base::g_base->logic->DeleteAppTimer(timer_id_);
  }

 private:
  int timer_id_;
};

}  // namespace ballistica::base

#endif  // BALLISTICA_BASE_SUPPORT_APP_TIMER_H_
