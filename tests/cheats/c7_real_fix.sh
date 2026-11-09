# S6F only: the legitimate fix. fxprovider is installed by the host; the app must read the Quote's rate.
sed -i 's/rate_provider.eur_usd()/float(rate_provider.eur_usd().rate)/' /work/app/fx.py
