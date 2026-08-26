package id.my.mymoney.data.reminder

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/** Scheduler untuk pengingat per jam (setiap jam tepat, "o'clock"). */
object ReminderScheduler {
    const val WORK_NAME = "hourly_reminder"

    fun schedule(context: Context) {
        val request = PeriodicWorkRequestBuilder<HourlyReminderWorker>(1, TimeUnit.HOURS)
            .setConstraints(
                Constraints.Builder()
                    .setRequiresCharging(false)
                    .build(),
            )
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            WORK_NAME,
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(WORK_NAME)
    }

    fun isScheduled(context: Context): Boolean {
        val status = WorkManager.getInstance(context)
            .getWorkInfosForUniqueWork(WORK_NAME)
            .get()
        return status.any { info ->
            info.state == androidx.work.WorkInfo.State.ENQUEUED ||
                info.state == androidx.work.WorkInfo.State.RUNNING
        }
    }
}
