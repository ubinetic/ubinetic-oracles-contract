import smartpy as sp

class Job:
    """Type used to specify Jobs later used by the scheduler.
    """
    def get_publish_type():
        """Type used for the publish entrypoint.
        """
        return sp.TRecord(
                executor=sp.TAddress, 
                script=sp.TBytes, 
                start=sp.TTimestamp, 
                end=sp.TTimestamp, 
                interval=sp.TNat, 
                fee=sp.TNat, 
                contract=sp.TAddress).layout(("executor",("script", ("start", ("end", ("interval", ("fee", "contract")))))))
    
    def make_publish(executor, script, start, end, interval, fee, contract):
        """Courtesy function typing a record to Job.get_publish_type() for us
        """
        return sp.set_type_expr(sp.record(executor=executor, 
                script=script,
                start=start, 
                end=end, 
                interval=interval, 
                fee=fee, 
                contract=contract), Job.get_publish_type())

    def get_type():
        """Type used for the storage
        """
        return sp.TRecord(status=sp.TNat, 
                start=sp.TTimestamp, 
                end=sp.TTimestamp, 
                interval=sp.TNat, 
                fee=sp.TNat, 
                contract=sp.TAddress).layout(("status", ("start", ("end", ("interval", ("fee", "contract"))))))

    def make(status, start, end, interval, fee, contract):
        """Courtesy function typing a record to Job.get_type() for us
        """
        return sp.set_type_expr(sp.record(status=status, 
                start=start, 
                end=end, 
                interval=interval, 
                fee=fee, 
                contract=contract), Job.get_type())

class Fulfill:
    """Type used by the datatransmitter to fulfill a Job
    """
    def get_type():
        """Type used in the fulfill entrypoint.
        """
        return sp.TRecord(script=sp.TBytes, payload=sp.TBytes).layout(("script","payload"))
    
    def make(script, payload):
        """Courtesy function typing a record to Fulfill.get_type() for us
        """
        return sp.set_type_expr(sp.record(script=script, 
                payload=payload), Fulfill.get_type())

class JobScheduler(sp.Contract):
    """Scheduler used to point the data transmitter to. This is where they fetch jobs and fulfill them.
    """
    def __init__(self, admin):
        """Initialises the storage with jobs and the admin mechanism
        """
        self.init(
            admin=admin,
            proposed_admin=admin,
            jobs=sp.big_map(tkey=sp.TAddress, tvalue=sp.TMap(sp.TBytes, Job.get_type()))
        )
    
    @sp.entry_point
    def publish(self, job):
        """Publish a job. Jobs are per executor and require an IPFS uri where the script is located. Jobs with the same executor and script
        will overwrite the previous definition. Once it's published the data transmitter first ack's the job and then at the requested
        timestamp will fulfill it. Only Admin can do this.
        """
        sp.set_type(job, Job.get_publish_type())
        sp.verify(sp.sender==self.data.admin)

        with sp.if_(~self.data.jobs.contains(job.executor)):
            self.data.jobs[job.executor] = {}
        self.data.jobs[job.executor][job.script] = Job.make(0, job.start, job.end, job.interval, job.fee, job.contract)

    @sp.entry_point
    def delete(self, executor, script):
        """Delete a job. Only Admin can do this.
        """
        sp.verify(sp.sender==self.data.admin)
        
        del self.data.jobs[executor][script]

    @sp.entry_point
    def propose_admin(self, proposed_admin):
        """Propose a new administrator. Only Admin can do this.
        """
        sp.verify(sp.sender==self.data.admin)        
        self.data.proposed_admin = proposed_admin

    @sp.entry_point
    def set_admin(self):
        """Set the proposed admin. Only proposed admin can do this.
        """
        sp.verify(sp.sender==self.data.proposed_admin)
        self.data.admin = self.data.proposed_admin

    @sp.entry_point
    def ack(self, script):
        """Acknowledge a job. Sender needs to be an executor and script needs to match the published jobs.
        """
        self.data.jobs[sp.sender][script].status = 1

    @sp.entry_point
    def fulfill(self, fulfill):
        """Fulfill a job and provide the expected payload to the receiving contract.
        """
        sp.set_type(fulfill, Fulfill.get_type())
        job = sp.local("job", self.data.jobs[sp.sender][fulfill.script])  
        callback_contract = sp.contract(Fulfill.get_type(), job.value.contract, "fulfill").open_some()
        sp.transfer(fulfill, sp.mutez(0), callback_contract)
        with sp.if_(job.value.end <= sp.now.add_seconds(sp.to_int(job.value.interval))):
            del self.data.jobs[sp.sender][fulfill.script]


class Fulfiller(sp.Contract):
    """This is a dummy contract that can be used to 'receive' and inspect the payload you receive from 
    the data transmitter.
    """
    def __init__(self):
        """This has only the payload as storage
        """
        self.init(
            payload=sp.bytes("0x00")
        )
        
    @sp.entry_point
    def default(self):
        """This entrypoint is there because single entrypoint is not allowed.
        """
        with sp.if_(sp.amount > sp.mutez(0)):
            sp.failwith("don't send me money")

    @sp.entry_point
    def fulfill(self, fulfill):
        """This entrypoint needs to be "fulfill" and accept a bytes payload (you can unpack in the implementation).
        """
        sp.set_type(fulfill, Fulfill.get_type())
        self.data.payload = fulfill.payload

if "templates" not in __name__:
    @sp.add_test(name = "Job Scheduler")
    def test():
        scenario = sp.test_scenario()
        scenario.h1("Job Scheduler")

        scenario.h2("Bootstrapping")
        administrator = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Robert")
        dan = sp.test_account("Dan")
        executor = sp.test_account("Executor")

        scenario.h2("Accounts")
        scenario.show([administrator, alice, bob, dan, executor])
        
        scheduler = JobScheduler(administrator.address)
        scenario += scheduler
        
        fulfiller = Fulfiller()
        scenario += fulfiller
        
        scenario.h2("Publishing jobs")
        script = sp.bytes('0x00')
        interval = 900
        fee = 1700
        start=sp.timestamp(0)
        end=sp.timestamp(1800)
        
        job = Job.make_publish(executor.address, script, start, end, interval, fee, fulfiller.address)
        scenario.p("Alice cannot publish, she is not admin")
        scenario += scheduler.publish(job).run(sender=alice.address, valid=False)
        
        scenario.p("Admin can publish")
        scenario += scheduler.publish(job).run(sender=administrator.address)
        
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].contract, fulfiller.address)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].fee, fee)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].interval, interval)

        scenario.p("Same script<>executor overrides")
        job = Job.make_publish(executor.address, script, start, end, interval, fee, sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'))
        scenario += scheduler.publish(job).run(sender=administrator.address)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].contract, sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'))

        job = Job.make_publish(executor.address, script, start, end, interval, fee, fulfiller.address)
        scenario += scheduler.publish(job).run(sender=administrator.address)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].contract, fulfiller.address)

        scenario.p("Same executor new script is new entry")
        script = sp.bytes('0x01')
        job = Job.make_publish(executor.address, script, start, end, interval, fee, sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'))
        scenario += scheduler.publish(job).run(sender=administrator.address)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].contract, sp.address('tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83'))
        script = sp.bytes('0x00')
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].contract, fulfiller.address)

        scenario.h2("Delete Jobs")
        scenario.p("Alice cannot delete, she is not admin")
        script = sp.bytes('0x01')
        scenario += scheduler.delete(executor=executor.address, script=script).run(sender=alice.address, valid=False)
        scenario.verify_equal(scheduler.data.jobs[executor.address].contains(script), True)
        
        scenario.p("Admin can delete")
        scenario += scheduler.delete(executor=executor.address, script=script).run(sender=administrator.address)
        scenario.verify_equal(scheduler.data.jobs[executor.address].contains(script), False)

        scenario.h2("Ack Jobs")
        script = sp.bytes('0x00')
        scenario.p("Alice cannot acknowledge a job")
        scenario += scheduler.ack(script).run(sender=alice.address, valid=False)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].status, 0)
        scenario.p("Admin cannot acknowledge a job")
        scenario += scheduler.ack(script).run(sender=administrator.address, valid=False)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].status, 0)
        scenario.p("Only an executor can acknowledge a job")
        scenario += scheduler.ack(script).run(sender=executor.address)
        scenario.verify_equal(scheduler.data.jobs[executor.address][script].status, 1)

        scenario.h2("Fulfill Jobs")
        payload = sp.pack(sp.address("tz3S9uYxmGahffYfcYURijrCGm1VBqiH4mPe"))

        scenario.p("Alice cannot fulfill a job")
        scenario += scheduler.fulfill(Fulfill.make(script,payload)).run(sender=alice.address, valid=False)
        scenario.verify_equal(fulfiller.data.payload, sp.bytes("0x00"))
        scenario.p("Admin cannot fulfill a job")
        scenario += scheduler.fulfill(Fulfill.make(script,payload)).run(sender=administrator.address, valid=False)
        scenario.verify_equal(fulfiller.data.payload, sp.bytes("0x00"))
        scenario.p("Only an executor can fulfill a job")
        scenario += scheduler.fulfill(Fulfill.make(script,payload)).run(sender=executor.address)
        scenario.verify_equal(fulfiller.data.payload, payload)

        scenario.p("Job is deleted when we passed end")
        payload = sp.pack(sp.address("tz1e3KTbvFmjfxjfse1RdEg2deoYjqoqgz83"))
        scenario += scheduler.fulfill(Fulfill.make(script, payload)).run(sender=executor.address, now=end)
        scenario.verify_equal(fulfiller.data.payload, payload)
        scenario.verify_equal(scheduler.data.jobs[executor.address].contains(script), False)