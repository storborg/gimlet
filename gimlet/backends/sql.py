from sqlalchemy import MetaData, Table, Column, types, create_engine, select
from sqlalchemy.orm import sessionmaker, scoped_session

from .base import BaseBackend


class SQLBackend(BaseBackend):

    def __init__(self, url, table_name='gimlet_channels'):
        engine = create_engine(url)
        meta = MetaData()
        meta.bind = engine
        sm = sessionmaker(bind=engine)
        self.sess = scoped_session(sm)

        self.table = Table(table_name, meta,
                           Column('id', types.Integer, primary_key=True),
                           Column('key', types.CHAR(32), nullable=False,
                                  unique=True),
                           Column('data', types.LargeBinary, nullable=False))
        self.table.create(checkfirst=True)

    def __setitem__(self, key, value):
        raw = self.serialize(value)
        try:
            # Check if this key exists with a SELECT FOR UPDATE, to protect
            # against a race with other concurrent writers of this key.
            q = self.table.select('1', for_update=True).\
                where(self.table.c.key == key)
            r = self.sess.execute(q).fetchone()
            if r:
                # If it exists, use an UPDATE.
                q = self.table.update().\
                    values(data=raw).\
                    where(self.table.c.key == key)
            else:
                # Otherwise INSERT.
                q = self.table.insert().values(key=key, data=raw)
            self.sess.execute(q)
            self.sess.commit()
        finally:
            self.sess.remove()

    def __getitem__(self, key):
        try:
            q = select([self.table.c.data], self.table.c.key == key)
            r = self.sess.execute(q).fetchone()
            if r:
                raw = r[0]
                return self.deserialize(raw)
            else:
                raise KeyError('key %r not found' % key)
        finally:
            self.sess.remove()
