import sbbf02


def parse(path):
    f = sbbf02.StarFile(path)
    f.parse()
    print 'Root block:', f.get_root()
    print
    print '==='
    print


#parse('universe/beta_73998977_11092106_-913658_12_10.world')
#parse('universe/alpha_-96872989_20655098_-22315521_6.world')
#parse('player/11475cedd80ead373c19a91de2e2c4d3.shipworld')

parse('universe/playerCodex.db')
parse('universe/playerQuests.db')

# This one is intense, but tests block size 2048 instead of 512.
#parse('assets/packed.pak')
