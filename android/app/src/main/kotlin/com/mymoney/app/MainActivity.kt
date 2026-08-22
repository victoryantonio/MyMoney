package com.mymoney.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.mymoney.app.data.local.TokenStore
import com.mymoney.app.ui.navigation.MyMoneyNavHost
import com.mymoney.app.ui.theme.MyMoneyTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var tokenStore: TokenStore

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MyMoneyTheme {
                MyMoneyNavHost(tokenStore = tokenStore)
            }
        }
    }
}
