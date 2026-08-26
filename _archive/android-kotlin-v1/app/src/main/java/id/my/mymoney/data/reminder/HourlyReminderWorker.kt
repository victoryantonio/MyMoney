package id.my.mymoney.data.reminder

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import id.my.mymoney.MainActivity
import id.my.mymoney.R

/**
 * Pengingat setiap jam (o'clock): mengingatkan pengguna mencatat
 * pengeluaran/pemasukan. Berjalan via WorkManager.
 */
class HourlyReminderWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val context = applicationContext
        createChannel(context)
        if (Build.VERSION.SDK_INT >= 33 &&
            NotificationManagerCompat.from(context).areNotificationsEnabled().not()
        ) {
            return Result.success() // izin notifikasi belum diberikan
        }
        showNotification(context)
        return Result.success()
    }

    private fun showNotification(context: Context) {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            context,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_notify)
            .setLargeIcon(
                BitmapFactory.decodeResource(context.resources, R.drawable.ic_notification_large),
            )
            .setContentTitle("Catat transaksi Anda")
            .setContentText("Jangan lupa mencatat pengeluaran/pemasukan Anda sekarang.")
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()
        try {
            NotificationManagerCompat.from(context).notify(REMINDER_ID, notification)
        } catch (e: SecurityException) {
            // Izin notifikasi belum diberikan — abaikan.
        }
    }

    private fun createChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Reminders",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Hourly reminder to record transactions"
            }
            val manager = context.getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    companion object {
        private const val CHANNEL_ID = "hourly_reminder"
        private const val REMINDER_ID = 1001
    }
}
